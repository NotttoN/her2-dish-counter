from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RoiRectangle:
    """Axis-aligned rectangular ROI stored in image coordinates."""

    x: float
    y: float
    width: float
    height: float
    roi_id: int = 1
    name: str = "ROI 1"
    roi_type: str = "tumor"

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.height

    def normalized(self) -> "RoiRectangle":
        x1 = min(self.x, self.x2)
        y1 = min(self.y, self.y2)
        return RoiRectangle(
            x=x1,
            y=y1,
            width=abs(self.width),
            height=abs(self.height),
            roi_id=self.roi_id,
            name=self.name,
            roi_type=self.roi_type,
        )

    def contains(self, x: float, y: float) -> bool:
        roi = self.normalized()
        return roi.x <= x <= roi.x2 and roi.y <= y <= roi.y2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoiRectangle":
        return cls(
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            width=float(data.get("width", 0)),
            height=float(data.get("height", 0)),
            roi_id=int(data.get("roi_id", 1)),
            name=str(data.get("name", "ROI 1")),
            roi_type=str(data.get("roi_type", "tumor")),
        ).normalized()


@dataclass
class NucleusCount:
    nucleus_id: int
    x: float
    y: float
    radius_x: float = 25.0
    radius_y: float = 18.0
    her2_black: int = 0
    small_cluster_count: int = 0
    large_cluster_count: int = 0
    manual_cluster_add: int = 0
    cep17_red: int = 0
    cluster_note: str = ""
    included: bool = True
    comment: str = ""

    @property
    def effective_her2(self) -> int:
        return (
            int(self.her2_black)
            + int(self.small_cluster_count) * 6
            + int(self.large_cluster_count) * 12
            + int(self.manual_cluster_add)
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NucleusCount":
        payload = dict(data)
        # Be tolerant of older/minimal JSON files.
        payload.setdefault("radius_x", 25.0)
        payload.setdefault("radius_y", 18.0)
        payload.setdefault("her2_black", 0)
        legacy_cluster_value = int(payload.pop("cluster_value", 0))
        payload.setdefault("small_cluster_count", 0)
        payload.setdefault("large_cluster_count", 0)
        payload.setdefault("manual_cluster_add", legacy_cluster_value)
        payload.setdefault("cep17_red", 0)
        payload.setdefault("cluster_note", "")
        payload.setdefault("included", True)
        payload.setdefault("comment", "")
        return cls(**payload)


@dataclass
class CaseProject:
    case_id: str = ""
    specimen_id: str = ""
    image_path: str = ""
    operator: str = ""
    ihc_score: str | None = None
    nuclei: list[NucleusCount] = field(default_factory=list)
    roi: RoiRectangle | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "specimen_id": self.specimen_id,
            "image_path": self.image_path,
            "operator": self.operator,
            "ihc_score": self.ihc_score,
            "nuclei": [n.to_dict() for n in self.nuclei],
            "roi": self.roi.to_dict() if self.roi else None,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CaseProject":
        roi_data = data.get("roi")
        # Backward-compatible read for experiments that stored rectangular ROIs in a list.
        if roi_data is None and data.get("rois"):
            first = data["rois"][0]
            if all(key in first for key in ("x", "y", "width", "height")):
                roi_data = first
        return cls(
            case_id=str(data.get("case_id", "")),
            specimen_id=str(data.get("specimen_id", "")),
            image_path=str(data.get("image_path", "")),
            operator=str(data.get("operator", "")),
            ihc_score=data.get("ihc_score"),
            nuclei=[NucleusCount.from_dict(item) for item in data.get("nuclei", [])],
            roi=RoiRectangle.from_dict(roi_data) if roi_data else None,
            notes=str(data.get("notes", "")),
        )
