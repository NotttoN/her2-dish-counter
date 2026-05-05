from __future__ import annotations

import json
from pathlib import Path

from .models import CaseProject


def save_project(project: CaseProject, path: str | Path) -> None:
    """Save a project to JSON."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)


def load_project(path: str | Path) -> CaseProject:
    """Load a project from JSON."""
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Project JSON root must be an object.")
    return CaseProject.from_dict(data)
