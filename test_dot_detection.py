from __future__ import annotations

import pytest

PIL_Image = pytest.importorskip("PIL.Image")
PIL_ImageDraw = pytest.importorskip("PIL.ImageDraw")

from her2dish.core.dot_detection import (
    DotCandidate,
    _merge_duplicate_red_candidates,
    detect_black_cluster_candidates,
    detect_black_dots,
    detect_red_dots,
    detect_red_dots_with_debug,
    params_from_sliders,
    red_detection_params_for_preset,
)
from her2dish.core.models import CaseProject, DetectionSettings, NucleusCount
from her2dish.core.project_io import load_project, save_project


def _blank_image():
    return PIL_Image.new("RGB", (120, 100), "white")


def _dot(draw, xy, radius, fill):
    x, y = xy
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)




def test_params_from_sliders_returns_clamped_detection_params():
    params = params_from_sliders(-10, 50, 125, 80)

    assert params.red_sensitivity == 0
    assert params.black_sensitivity == 50
    assert params.haze_rejection == 100
    assert params.cluster_sensitivity == 80
    assert params.red_min_area > 0
    assert params.black_cluster_max_area > params.black_cluster_min_area


def test_red_sensitivity_slider_moves_thresholds_toward_pale_red_detection():
    low = params_from_sliders(10, 50, 50, 50)
    high = params_from_sliders(90, 50, 50, 50)

    assert high.red_saturation_threshold < low.red_saturation_threshold
    assert high.red_value_threshold < low.red_value_threshold
    assert high.red_min_area < low.red_min_area
    assert high.red_max_area > low.red_max_area
    assert high.red_circularity_threshold < low.red_circularity_threshold


def test_black_sensitivity_slider_moves_thresholds_toward_faint_black_detection():
    low = params_from_sliders(50, 10, 50, 50)
    high = params_from_sliders(50, 90, 50, 50)

    assert high.black_darkness_threshold > low.black_darkness_threshold
    assert high.black_min_area < low.black_min_area
    assert high.black_max_area > low.black_max_area
    assert high.black_local_contrast_threshold < low.black_local_contrast_threshold
    assert high.black_circularity_threshold < low.black_circularity_threshold


def test_haze_rejection_slider_moves_thresholds_toward_stronger_rejection():
    low = params_from_sliders(50, 50, 10, 50)
    high = params_from_sliders(50, 50, 90, 50)

    assert high.red_haze_saturation_threshold > low.red_haze_saturation_threshold
    assert high.red_haze_local_contrast_threshold > low.red_haze_local_contrast_threshold
    assert high.red_haze_area_threshold < low.red_haze_area_threshold
    assert high.red_haze_rejection_strength > low.red_haze_rejection_strength


def test_cluster_sensitivity_slider_moves_thresholds_toward_more_review_candidates():
    low = params_from_sliders(50, 50, 50, 10)
    high = params_from_sliders(50, 50, 50, 90)

    assert high.black_cluster_min_area < low.black_cluster_min_area
    assert high.black_cluster_max_area > low.black_cluster_max_area
    assert high.black_cluster_darkness_threshold > low.black_cluster_darkness_threshold
    assert high.black_cluster_compactness_threshold < low.black_cluster_compactness_threshold

def test_detect_black_dots_counts_synthetic_candidates():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    for xy in [(45, 45), (60, 50), (75, 55)]:
        _dot(draw, xy, 3, (20, 18, 16))

    candidates = detect_black_dots(image, nucleus_x=60, nucleus_y=50, radius_x=40, radius_y=30)

    assert len(candidates) == 3
    assert {c.color_type for c in candidates} == {"black"}
    assert all(c.area >= 8 for c in candidates)


def test_detect_red_dots_counts_synthetic_candidates():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    for xy in [(52, 45), (70, 55)]:
        _dot(draw, xy, 3, (220, 20, 70))

    candidates = detect_red_dots(image, nucleus_x=60, nucleus_y=50, radius_x=35, radius_y=28)

    assert len(candidates) == 2
    assert {c.color_type for c in candidates} == {"red"}


def test_detect_red_dots_counts_pure_red_standard_candidates():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    for xy in [(52, 45), (70, 55)]:
        _dot(draw, xy, 3, (255, 0, 0))

    candidates = detect_red_dots(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Standard")
    )

    assert len(candidates) == 2
    assert {c.color_type for c in candidates} == {"red"}


def test_detect_red_dots_counts_magenta_standard_candidates():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    for xy in [(52, 45), (70, 55)]:
        _dot(draw, xy, 3, (220, 45, 220))

    candidates = detect_red_dots(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Standard")
    )

    assert len(candidates) == 2


def test_sensitive_detects_pale_red_that_standard_rejects():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    for xy in [(52, 45), (70, 55)]:
        _dot(draw, xy, 3, (230, 200, 205))

    standard = detect_red_dots(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Standard")
    )
    sensitive = detect_red_dots(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Sensitive")
    )

    assert standard == []
    assert len(sensitive) == 2


def test_red_detection_debug_reports_nonzero_mask_values():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    for xy in [(52, 45), (70, 55)]:
        _dot(draw, xy, 3, (220, 45, 220))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Standard")
    )

    assert result.stats.mask_pixels > 0
    assert result.stats.connected_components == 2
    assert result.stats.detected_candidates == 2


def test_detection_excludes_dots_outside_nucleus_roi():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (60, 50), 3, (15, 15, 15))
    _dot(draw, (100, 50), 3, (15, 15, 15))
    _dot(draw, (60, 90), 3, (220, 20, 70))
    _dot(draw, (70, 50), 3, (220, 20, 70))

    black = detect_black_dots(image, nucleus_x=60, nucleus_y=50, radius_x=20, radius_y=18)
    red = detect_red_dots(image, nucleus_x=60, nucleus_y=50, radius_x=20, radius_y=18)

    assert len(black) == 1
    assert len(red) == 1
    assert black[0].x == pytest.approx(60.5, abs=1.0)
    assert red[0].x == pytest.approx(70.5, abs=1.0)


def test_detection_filters_tiny_dust():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    draw.point((50, 50), fill=(10, 10, 10))
    draw.point((51, 50), fill=(10, 10, 10))
    _dot(draw, (70, 50), 3, (10, 10, 10))

    candidates = detect_black_dots(image, nucleus_x=60, nucleus_y=50, radius_x=35, radius_y=25)

    assert len(candidates) == 1
    assert candidates[0].area > 8


def test_json_roundtrip_preserves_dot_candidates(tmp_path):
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (52, 50), 3, (10, 10, 10))
    _dot(draw, (68, 50), 3, (220, 20, 70))
    nucleus = NucleusCount(nucleus_id=1, x=60, y=50)
    nucleus.black_dot_candidates = detect_black_dots(image, 60, 50, 35, 25)
    nucleus.red_dot_candidates = detect_red_dots(image, 60, 50, 35, 25)
    project = CaseProject(nuclei=[nucleus])

    path = tmp_path / "project.json"
    save_project(project, path)
    loaded = load_project(path)

    assert len(loaded.nuclei[0].black_dot_candidates) == 1
    assert len(loaded.nuclei[0].red_dot_candidates) == 1
    assert loaded.nuclei[0].black_dot_candidates[0].color_type == "black"
    assert loaded.nuclei[0].red_dot_candidates[0].color_type == "red"


def test_detection_uses_adjusted_nucleus_roi():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (40, 50), 3, (15, 15, 15))
    _dot(draw, (82, 50), 3, (15, 15, 15))

    initial = detect_black_dots(image, nucleus_x=60, nucleus_y=50, radius_x=35, radius_y=25)
    resized = detect_black_dots(image, nucleus_x=60, nucleus_y=50, radius_x=15, radius_y=25)
    moved = detect_black_dots(image, nucleus_x=82, nucleus_y=50, radius_x=10, radius_y=10)

    assert len(initial) == 2
    assert resized == []
    assert len(moved) == 1
    assert moved[0].x == pytest.approx(82.5, abs=1.0)


def test_sensitive_counts_large_red_component_as_one_cep17_candidate():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (60, 50), 8, (220, 20, 70))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Sensitive")
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].color_type == "red"
    assert result.stats.large_red_candidates == 0


def test_sensitive_keeps_irregular_red_dot_candidate():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    draw.ellipse((48, 45, 72, 55), fill=(220, 20, 70))
    draw.rectangle((58, 43, 70, 47), fill=(220, 20, 70))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Sensitive")
    )

    assert len(result.candidates) >= 1
    assert result.stats.area_pass_components >= 1


def test_sensitive_splits_or_retains_close_red_dots():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (56, 50), 4, (220, 20, 70))
    _dot(draw, (64, 50), 4, (220, 20, 70))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Sensitive")
    )

    assert len(result.candidates) in {1, 2}
    assert {candidate.color_type for candidate in result.candidates} == {"red"}


def test_sensitive_excludes_large_red_dot_outside_nucleus_roi():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (60, 50), 8, (220, 20, 70))
    _dot(draw, (105, 50), 8, (220, 20, 70))

    candidates = detect_red_dots(
        image, 60, 50, 25, 20, red_detection_params_for_preset("Sensitive")
    )

    assert len(candidates) == 1
    assert candidates[0].x == pytest.approx(60.5, abs=1.0)


def test_black_dot_only_is_not_detected_as_cep17_candidate():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (60, 50), 4, (15, 15, 15))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Standard")
    )

    assert result.candidates == []
    assert result.overlap_candidates == []


def test_red_dot_with_black_overlap_is_counted_as_cep17_without_overlap_review():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (60, 50), 7, (220, 20, 70))
    _dot(draw, (60, 50), 3, (15, 15, 15))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Standard")
    )
    black = detect_black_dots(image, 60, 50, 35, 28, red_detection_params_for_preset("Standard"))

    assert len(result.candidates) == 1
    assert result.candidates[0].color_type == "red"
    assert len(black) == 1
    assert result.overlap_candidates == []
    assert result.stats.overlap_review_candidates == 0


def test_large_irregular_red_dot_is_one_cep17_candidate():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    draw.ellipse((45, 42, 72, 57), fill=(220, 20, 70))
    draw.polygon([(58, 38), (78, 49), (61, 60)], fill=(220, 20, 70))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Sensitive")
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].color_type == "red"
    assert result.overlap_candidates == []


def test_black_split_red_component_is_not_overcounted_as_multiple_cep17():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    draw.ellipse((48, 42, 72, 58), fill=(220, 20, 70))
    draw.rectangle((58, 41, 62, 59), fill=(15, 15, 15))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Sensitive")
    )

    assert len(result.candidates) <= 1


def test_red_connected_components_are_final_cep17_candidates():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (52, 45), 4, (220, 20, 70))
    _dot(draw, (72, 55), 4, (220, 20, 70))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Standard")
    )

    assert result.stats.connected_components == 2
    assert result.stats.area_pass_components == 2
    assert result.stats.circularity_pass_components == 2
    assert len(result.candidates) == 2
    assert result.stats.final_cep17_candidates == 2


def test_large_red_component_is_one_final_cep17_candidate():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    draw.ellipse((43, 35, 78, 66), fill=(220, 20, 70))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Sensitive")
    )

    assert result.stats.connected_components == 1
    assert len(result.candidates) == 1
    assert result.candidates[0].color_type == "red"
    assert result.stats.large_red_candidates == 0
    assert result.stats.final_cep17_candidates == 1


def test_irregular_red_component_is_one_final_cep17_candidate():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    draw.polygon([(45, 46), (58, 38), (78, 48), (67, 61), (50, 58)], fill=(220, 20, 70))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Sensitive")
    )

    assert result.stats.connected_components == 1
    assert len(result.candidates) == 1
    assert result.stats.final_cep17_candidates == 1


def test_duplicate_red_candidates_from_same_component_are_merged():
    candidates, merged_count = _merge_duplicate_red_candidates(
        [
            (1, DotCandidate(x=50.0, y=50.0, area=20.0, confidence=0.7, color_type="red")),
            (1, DotCandidate(x=53.0, y=50.0, area=25.0, confidence=0.8, color_type="red")),
        ],
        merge_distance_px=6.0,
    )

    assert len(candidates) == 1
    assert merged_count == 1
    assert candidates[0].color_type == "red"


def test_near_duplicate_red_candidates_are_merged_by_distance():
    candidates, merged_count = _merge_duplicate_red_candidates(
        [
            (1, DotCandidate(x=50.0, y=50.0, area=20.0, confidence=0.7, color_type="red")),
            (2, DotCandidate(x=55.0, y=51.0, area=22.0, confidence=0.6, color_type="red")),
        ],
        merge_distance_px=6.0,
    )

    assert len(candidates) == 1
    assert merged_count == 1


def test_black_dot_and_nearby_red_dot_are_separate_candidates():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (55, 50), 3, (15, 15, 15))
    _dot(draw, (65, 50), 3, (220, 20, 70))

    black = detect_black_dots(image, 60, 50, 35, 28, red_detection_params_for_preset("Standard"))
    red = detect_red_dots(image, 60, 50, 35, 28, red_detection_params_for_preset("Standard"))

    assert len(black) == 1
    assert len(red) == 1


def test_very_dark_reddish_black_dot_is_kept_as_her2_not_cep17():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (60, 50), 3, (95, 25, 20))

    black = detect_black_dots(image, 60, 50, 35, 28, red_detection_params_for_preset("Standard"))
    red = detect_red_dots(image, 60, 50, 35, 28, red_detection_params_for_preset("Standard"))

    assert len(black) == 1
    assert red == []


def test_sensitive_rejects_black_dominant_reddish_candidate():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (60, 50), 4, (118, 38, 32))

    red = detect_red_dots(image, 60, 50, 35, 28, params_from_sliders(95, 50, 50, 50))

    assert red == []


def test_json_roundtrip_preserves_detection_settings(tmp_path):
    project = CaseProject(
        detection_settings=DetectionSettings(
            preset="Custom",
            red_sensitivity=72,
            black_sensitivity=64,
            haze_rejection=83,
            cluster_sensitivity=91,
        )
    )

    path = tmp_path / "settings.json"
    save_project(project, path)
    loaded = load_project(path)

    assert loaded.detection_settings.preset == "Custom"
    assert loaded.detection_settings.red_sensitivity == 72
    assert loaded.detection_settings.black_sensitivity == 64
    assert loaded.detection_settings.haze_rejection == 83
    assert loaded.detection_settings.cluster_sensitivity == 91


def test_missing_detection_settings_loads_defaults(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text('{"nuclei": []}', encoding="utf-8")

    loaded = load_project(path)

    assert loaded.detection_settings.preset == "Standard"
    assert loaded.detection_settings.red_sensitivity == 50
    assert loaded.detection_settings.black_sensitivity == 50
    assert loaded.detection_settings.haze_rejection == 50
    assert loaded.detection_settings.cluster_sensitivity == 50


def test_slider_sensitivity_changes_synthetic_detection_counts():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (48, 50), 2, (235, 200, 205))
    _dot(draw, (62, 50), 2, (235, 200, 205))
    _dot(draw, (76, 50), 2, (132, 130, 128))
    _dot(draw, (90, 50), 2, (132, 130, 128))

    low = params_from_sliders(10, 10, 50, 50)
    high = params_from_sliders(95, 95, 50, 50)

    assert len(detect_red_dots(image, 60, 50, 45, 28, high)) > len(detect_red_dots(image, 60, 50, 45, 28, low))
    assert len(detect_black_dots(image, 60, 50, 45, 28, high)) > len(detect_black_dots(image, 60, 50, 45, 28, low))


def test_high_haze_rejection_removes_broad_pale_red_component():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    draw.ellipse((20, 30, 70, 65), fill=(230, 195, 200))

    low_haze = detect_red_dots_with_debug(image, 60, 50, 55, 40, params_from_sliders(95, 50, 10, 50))
    high_haze = detect_red_dots_with_debug(image, 60, 50, 55, 40, params_from_sliders(95, 50, 95, 50))

    assert len(high_haze.candidates) < len(low_haze.candidates)
    assert high_haze.stats.red_haze_rejected_components == 1


def test_cluster_candidate_is_review_only_candidate_type():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (60, 50), 7, (35, 33, 31))

    candidates = detect_black_cluster_candidates(image, 60, 50, 35, 28, params_from_sliders(50, 50, 50, 95))

    assert len(candidates) == 1
    assert candidates[0].color_type == "black_cluster_review"


def test_overlapping_red_and_black_signals_are_independent_candidates():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (58, 50), 5, (220, 20, 70))
    _dot(draw, (62, 50), 3, (15, 15, 15))

    params = red_detection_params_for_preset("Standard")
    red_result = detect_red_dots_with_debug(image, 60, 50, 35, 28, params)
    black = detect_black_dots(image, 60, 50, 35, 28, params)

    assert len(red_result.candidates) == 1
    assert len(black) == 1
    assert red_result.overlap_candidates == []
    assert {candidate.color_type for candidate in red_result.candidates} == {"red"}


def test_red_signal_inside_black_cluster_is_cep17_and_cluster_is_review_only():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (60, 50), 9, (35, 33, 31))
    _dot(draw, (60, 50), 3, (220, 20, 70))

    params = params_from_sliders(80, 50, 50, 95)
    red_result = detect_red_dots_with_debug(image, 60, 50, 35, 28, params)
    clusters = detect_black_cluster_candidates(image, 60, 50, 35, 28, params)
    black_dots = detect_black_dots(image, 60, 50, 35, 28, params)
    nucleus = NucleusCount(nucleus_id=1, x=60, y=50)
    nucleus.red_dot_candidates = red_result.candidates
    nucleus.black_dot_candidates = black_dots
    nucleus.black_cluster_candidates = clusters
    nucleus.her2_black = len(nucleus.black_dot_candidates)
    nucleus.cep17_red = len(nucleus.red_dot_candidates)

    assert len(red_result.candidates) == 1
    assert len(clusters) == 1
    assert clusters[0].color_type == "black_cluster_review"
    assert nucleus.her2_black == len(black_dots)
    assert nucleus.small_cluster_count == 0
    assert nucleus.large_cluster_count == 0
    assert nucleus.cep17_red == 1


def test_new_detection_never_emits_overlap_review_candidate_type():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (60, 50), 7, (220, 20, 70))
    _dot(draw, (60, 50), 3, (15, 15, 15))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Standard")
    )

    assert result.overlap_candidates == []
    assert all(candidate.color_type != "overlap_review" for candidate in result.candidates)
    assert result.stats.overlap_review_candidates == 0
