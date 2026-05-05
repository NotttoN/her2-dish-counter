from __future__ import annotations

from .models import RoiPolygon


def rectangle_roi(roi_id: int, name: str, x1: float, y1: float, x2: float, y2: float, roi_type: str = "tumor") -> RoiPolygon:
    """Create a rectangular ROI polygon from two corners."""
    left, right = sorted([float(x1), float(x2)])
    top, bottom = sorted([float(y1), float(y2)])
    return RoiPolygon(
        roi_id=roi_id,
        name=name,
        points=[(left, top), (right, top), (right, bottom), (left, bottom)],
        roi_type=roi_type,
    )
