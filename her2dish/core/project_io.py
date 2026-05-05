from __future__ import annotations
import json
from pathlib import Path
from .models import CaseProject

def save_project(project: CaseProject, path: str | Path) -> None:
    Path(path).write_text(json.dumps(project.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')

def load_project(path: str | Path) -> CaseProject:
    return CaseProject.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))
