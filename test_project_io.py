import csv

import pytest

from her2dish.core.models import CaseProject, DetectionSettings, NucleusCount, RoiRectangle
from her2dish.core.project_io import load_project, save_project
from her2dish.core.exporters import export_csv, export_annotated_png
from her2dish.core.scoring import calculate_score


def test_save_and_load_project_with_roi(tmp_path):
    project = CaseProject(
        case_id="case-001",
        specimen_id="specimen-001",
        image_path="image.png",
        operator="tester",
        roi=RoiRectangle(x=5, y=6, width=100, height=80),
        nuclei=[NucleusCount(nucleus_id=1, x=10.5, y=20.5, her2_black=4, cep17_red=2)],
    )
    path = tmp_path / "project.json"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded.case_id == "case-001"
    assert loaded.specimen_id == "specimen-001"
    assert loaded.image_path == "image.png"
    assert len(loaded.nuclei) == 1
    assert loaded.roi is not None
    assert loaded.roi.contains(10.5, 20.5)


def test_manual_count_and_exports_with_source_image(tmp_path):
    pillow = pytest.importorskip("PIL.Image")
    image_path = tmp_path / "source.png"
    pillow.new("RGB", (320, 240), "white").save(image_path)

    nuclei = [
        NucleusCount(nucleus_id=1, x=100, y=120, her2_black=4, small_cluster_count=1, cep17_red=2),
        NucleusCount(nucleus_id=2, x=180, y=200, her2_black=2, manual_cluster_add=1, cep17_red=2, included=False),
    ]
    project = CaseProject(
        case_id="c",
        specimen_id="s",
        image_path=str(image_path),
        roi=RoiRectangle(50, 60, 200, 120),
        nuclei=nuclei,
        detection_settings=DetectionSettings(
            preset="Custom", red_sensitivity=61, black_sensitivity=62, haze_rejection=63, cluster_sensitivity=64
        ),
    )
    score = calculate_score(project.nuclei)
    assert score.total_her2 == 10
    assert score.total_cep17 == 2

    csv_path = tmp_path / "counts.csv"
    export_csv(project, csv_path)
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["radius_x"] == "25.0"
    assert rows[0]["small_cluster_count"] == "1"
    assert rows[0]["large_cluster_count"] == "0"
    assert rows[0]["manual_cluster_add"] == "0"
    assert rows[0]["effective_her2"] == "10"
    assert rows[0]["detected_black_dot_count"] == "0"
    assert rows[0]["detected_red_dot_count"] == "0"
    assert rows[0]["detected_large_red_count"] == "0"
    assert "overlap_review_candidate_count" not in rows[0]
    assert rows[0]["black_cluster_review_candidate_count"] == "0"
    assert rows[0]["detection_red_sensitivity"] == "61"
    assert rows[0]["detection_black_sensitivity"] == "62"
    assert rows[0]["detection_haze_rejection"] == "63"
    assert rows[0]["detection_cluster_sensitivity"] == "64"

    png_path = tmp_path / "annotated.png"
    export_annotated_png(project, png_path)
    assert png_path.exists()
    exported = pillow.open(png_path)
    assert exported.width > 320
    assert exported.height > 240


def test_annotated_png_expands_canvas_for_disclaimer_and_bottom_annotations(tmp_path):
    pillow = pytest.importorskip("PIL.Image")
    image_path = tmp_path / "source.png"
    pillow.new("RGB", (120, 90), "white").save(image_path)

    project = CaseProject(
        image_path=str(image_path),
        roi=RoiRectangle(8, 8, 100, 72),
        nuclei=[NucleusCount(nucleus_id=1, x=95, y=86, radius_x=25, radius_y=18, her2_black=3, cep17_red=2)],
    )

    png_path = tmp_path / "annotated-expanded.png"
    export_annotated_png(project, png_path)

    exported = pillow.open(png_path)
    assert exported.width >= 520
    assert exported.height > 90


def test_nucleus_radius_roundtrip_and_legacy_defaults(tmp_path):
    project = CaseProject(
        nuclei=[NucleusCount(nucleus_id=1, x=33, y=44, radius_x=31.5, radius_y=12.5)]
    )
    path = tmp_path / "radius-project.json"
    save_project(project, path)

    loaded = load_project(path)
    assert loaded.nuclei[0].radius_x == pytest.approx(31.5)
    assert loaded.nuclei[0].radius_y == pytest.approx(12.5)

    legacy_path = tmp_path / "legacy-project.json"
    legacy_path.write_text(
        '{"nuclei": [{"nucleus_id": 1, "x": 10, "y": 20}]}', encoding="utf-8"
    )
    legacy = load_project(legacy_path)
    assert legacy.nuclei[0].radius_x == pytest.approx(25.0)
    assert legacy.nuclei[0].radius_y == pytest.approx(18.0)


def test_annotated_png_uses_per_nucleus_radius(tmp_path):
    pillow = pytest.importorskip("PIL.Image")
    image_path = tmp_path / "source.png"
    pillow.new("RGB", (100, 80), "white").save(image_path)
    project = CaseProject(
        image_path=str(image_path),
        nuclei=[NucleusCount(nucleus_id=1, x=40, y=40, radius_x=10, radius_y=8)],
    )

    png_path = tmp_path / "annotated-radius.png"
    export_annotated_png(project, png_path)
    exported = pillow.open(png_path).convert("RGB")

    # The source image is pasted at (28, 28); custom-radius ellipse reaches x=40+10, y=40.
    assert exported.getpixel((28 + 50, 28 + 40)) != (255, 255, 255)
    # A fixed 25 px radius would draw near x=40+25, but the adjusted 10 px ROI should not.
    assert exported.getpixel((28 + 65, 28 + 40)) == (255, 255, 255)


def test_save_project_omits_legacy_overlap_candidates(tmp_path):
    from her2dish.core.dot_detection import DotCandidate

    nucleus = NucleusCount(nucleus_id=1, x=10, y=20)
    nucleus.overlap_dot_candidates.append(DotCandidate(x=10, y=20, area=25, color_type="overlap_review"))
    project = CaseProject(nuclei=[nucleus])

    path = tmp_path / "project.json"
    save_project(project, path)

    saved = path.read_text(encoding="utf-8")
    assert "overlap_dot_candidates" not in saved
    assert "overlap_review" not in saved


def test_load_project_accepts_legacy_overlap_candidates(tmp_path):
    path = tmp_path / "legacy-overlap.json"
    path.write_text(
        '{"nuclei": [{"nucleus_id": 1, "x": 10, "y": 20, "overlap_dot_candidates": [{"x": 10, "y": 20, "area": 25}]}]}',
        encoding="utf-8",
    )

    loaded = load_project(path)

    assert len(loaded.nuclei) == 1
    assert len(loaded.nuclei[0].overlap_dot_candidates) == 1
