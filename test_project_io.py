import csv

import pytest

from her2dish.core.models import CaseProject, NucleusCount, RoiRectangle
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
        NucleusCount(nucleus_id=1, x=100, y=120, her2_black=4, cep17_red=2),
        NucleusCount(nucleus_id=2, x=180, y=200, her2_black=2, cep17_red=2, cluster_value=1, included=False),
    ]
    project = CaseProject(case_id="c", specimen_id="s", image_path=str(image_path), roi=RoiRectangle(50, 60, 200, 120), nuclei=nuclei)
    score = calculate_score(project.nuclei)
    assert score.total_her2 == 4
    assert score.total_cep17 == 2

    csv_path = tmp_path / "counts.csv"
    export_csv(project, csv_path)
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["radius_x"] == "25.0"
    assert rows[0]["effective_her2"] == "4"

    png_path = tmp_path / "annotated.png"
    export_annotated_png(project, png_path)
    assert png_path.exists()
    exported = pillow.open(png_path)
    assert exported.size == (320, 240)
