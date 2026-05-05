from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class NucleusCount:
    nucleus_id: int
    x: float
    y: float
    radius_x: float = 25.0
    radius_y: float = 18.0
    her2_black: int = 0
    cep17_red: int = 0
    cluster_value: int = 0
    cluster_note: str = ""
    included: bool = True
    comment: str = ""

    @property
    def effective_her2(self) -> int:
        return int(self.her2_black) + int(self.cluster_value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NucleusCount":
        return cls(**data)


@dataclass
class RoiPolygon:
    roi_id: int
    name: str
    points: list[tuple[float, float]]
    roi_type: str = "tumor"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["points"] = [[float(x), float(y)] for x, y in self.points]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoiPolygon":
        points = [(float(x), float(y)) for x, y in data.get("points", [])]
        return cls(
            roi_id=int(data["roi_id"]),
            name=str(data.get("name", "ROI")),
            points=points,
            roi_type=str(data.get("roi_type", "tumor")),
        )


@dataclass
class CaseProject:
    case_id: str = ""
    specimen_id: str = ""
    image_path: str = ""
    operator: str = ""
    ihc_score: str | None = None
    nuclei: list[NucleusCount] = field(default_factory=list)
    rois: list[RoiPolygon] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "specimen_id": self.specimen_id,
            "image_path": self.image_path,
            "operator": self.operator,
            "ihc_score": self.ihc_score,
            "nuclei": [n.to_dict() for n in self.nuclei],
            "rois": [r.to_dict() for r in self.rois],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CaseProject":
        return cls(
            case_id=str(data.get("case_id", "")),
            specimen_id=str(data.get("specimen_id", "")),
            image_path=str(data.get("image_path", "")),
            operator=str(data.get("operator", "")),
            ihc_score=data.get("ihc_score"),
            nuclei=[NucleusCount.from_dict(item) for item in data.get("nuclei", [])],
            rois=[RoiPolygon.from_dict(item) for item in data.get("rois", [])],
            notes=str(data.get("notes", "")),
        )
