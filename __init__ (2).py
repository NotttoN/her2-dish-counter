from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import CaseProject
from .scoring import calculate_score


def nuclei_to_dataframe(project: CaseProject) -> pd.DataFrame:
    rows = []
    for nucleus in project.nuclei:
        rows.append(
            {
                "case_id": project.case_id,
                "specimen_id": project.specimen_id,
                "image_path": project.image_path,
                "operator": project.operator,
                "nucleus_id": nucleus.nucleus_id,
                "x": nucleus.x,
                "y": nucleus.y,
                "included": nucleus.included,
                "her2_black": nucleus.her2_black,
                "cep17_red": nucleus.cep17_red,
                "cluster_value": nucleus.cluster_value,
                "cluster_note": nucleus.cluster_note,
                "effective_her2": nucleus.effective_her2,
                "comment": nucleus.comment,
            }
        )
    return pd.DataFrame(rows)


def summary_to_dataframe(project: CaseProject) -> pd.DataFrame:
    result = calculate_score(project.nuclei)
    return pd.DataFrame(
        [
            {
                "case_id": project.case_id,
                "specimen_id": project.specimen_id,
                "image_path": project.image_path,
                "operator": project.operator,
                "included_cell_count": result.included_cell_count,
                "total_her2": result.total_her2,
                "total_cep17": result.total_cep17,
                "her2_cep17_ratio": result.her2_cep17_ratio,
                "average_her2_copy_number": result.average_her2_copy_number,
                "ish_group": result.ish_group,
                "warning_messages": " | ".join(result.warnings),
            }
        ]
    )


def export_csv(project: CaseProject, nuclei_csv_path: str | Path, summary_csv_path: str | Path | None = None) -> None:
    """Export nuclei CSV and optional summary CSV."""
    nuclei_path = Path(nuclei_csv_path)
    nuclei_path.parent.mkdir(parents=True, exist_ok=True)
    nuclei_to_dataframe(project).to_csv(nuclei_path, index=False)
    if summary_csv_path is not None:
        summary_path = Path(summary_csv_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_to_dataframe(project).to_csv(summary_path, index=False)
