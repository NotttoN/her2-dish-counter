import pytest
from her2dish.core.models import CaseProject, NucleusCount
from her2dish.core.project_io import load_project, save_project
from her2dish.core.exporters import export_csv, export_annotated_png
from her2dish.core.scoring import calculate_score


def test_save_and_load_project(tmp_path):
    project = CaseProject(
        case_id="case-001",
        specimen_id="specimen-001",
        image_path="image.png",
        operator="tester",
        nuclei=[NucleusCount(nucleus_id=1, x=10.5, y=20.5, her2_black=4, cep17_red=2)],
    )
    path = tmp_path / "project.json"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded.case_id == "case-001"
    assert loaded.specimen_id == "specimen-001"
    assert loaded.image_path == "image.png"
    assert len(loaded.nuclei) == 1


def test_manual_count_and_exports(tmp_path):
    nuclei = [
        NucleusCount(nucleus_id=1, x=100, y=120, her2_black=4, cep17_red=2),
        NucleusCount(nucleus_id=2, x=180, y=200, her2_black=2, cep17_red=2, cluster_value=1),
    ]
    project = CaseProject(case_id="c", specimen_id="s", nuclei=nuclei)
    score = calculate_score(project.nuclei)
    assert score.total_her2 == 7
    assert score.total_cep17 == 4

    csv_path = tmp_path / "counts.csv"
    export_csv(project, csv_path)
    assert csv_path.exists()

    pytest.importorskip("PIL")
    png_path = tmp_path / "annotated.png"
    export_annotated_png(project, png_path)
    assert png_path.exists()
