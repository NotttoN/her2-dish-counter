from __future__ import annotations

import pytest

PIL_Image = pytest.importorskip("PIL.Image")
PIL_ImageDraw = pytest.importorskip("PIL.ImageDraw")

from her2dish.core.dot_detection import (
    detect_black_dots,
    detect_red_dots,
    detect_red_dots_with_debug,
    red_detection_params_for_preset,
)
from her2dish.core.models import CaseProject, NucleusCount
from her2dish.core.project_io import load_project, save_project


def _blank_image():
    return PIL_Image.new("RGB", (120, 100), "white")


def _dot(draw, xy, radius, fill):
    x, y = xy
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


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


def test_sensitive_detects_large_red_dot_as_review_candidate():
    image = _blank_image()
    draw = PIL_ImageDraw.Draw(image)
    _dot(draw, (60, 50), 8, (220, 20, 70))

    result = detect_red_dots_with_debug(
        image, 60, 50, 35, 28, red_detection_params_for_preset("Sensitive")
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].color_type == "large_red"
    assert result.stats.large_red_candidates == 1


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
    if len(result.candidates) == 1:
        assert result.candidates[0].color_type == "large_red"
    else:
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
