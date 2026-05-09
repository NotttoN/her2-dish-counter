from __future__ import annotations

from dataclasses import asdict, dataclass
import colorsys
import math
from typing import Any, Iterable


@dataclass
class DotCandidate:
    """Semi-automatic dot candidate inside one clicked nucleus ROI."""

    x: float
    y: float
    area: float
    confidence: float | None = None
    color_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any], default_color_type: str = "") -> "DotCandidate":
        return cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            area=float(data.get("area", 0.0)),
            confidence=(None if data.get("confidence") is None else float(data.get("confidence", 0.0))),
            color_type=str(data.get("color_type", default_color_type)),
        )


@dataclass(frozen=True)
class DotDetectionParams:
    """Fixed v0.2.0 defaults, grouped so future UI controls can edit them."""

    black_min_area: float = 8.0
    black_max_area: float = 220.0
    black_threshold: int = 115
    red_min_area: float = 8.0
    red_max_area: float = 220.0
    red_hue_range: tuple[tuple[float, float], ...] = ((0.0, 25.0), (320.0, 360.0))
    red_saturation_threshold: float = 0.35
    red_value_threshold: float = 0.25
    circularity_threshold: float = 0.45


DEFAULT_DOT_DETECTION_PARAMS = DotDetectionParams()


def detect_black_dots(
    image_rgb: Any,
    nucleus_x: float,
    nucleus_y: float,
    radius_x: float,
    radius_y: float,
    params: DotDetectionParams | None = None,
) -> list[DotCandidate]:
    """Detect dark HER2 dot candidates within the selected elliptical nucleus ROI."""

    p = params or DEFAULT_DOT_DETECTION_PARAMS
    return _detect_components(
        image_rgb,
        nucleus_x,
        nucleus_y,
        radius_x,
        radius_y,
        pixel_predicate=lambda r, g, b: _is_black_candidate_pixel(r, g, b, p),
        min_area=p.black_min_area,
        max_area=p.black_max_area,
        circularity_threshold=p.circularity_threshold,
        color_type="black",
        confidence_func=lambda pixels: _black_confidence(pixels, p),
    )


def detect_red_dots(
    image_rgb: Any,
    nucleus_x: float,
    nucleus_y: float,
    radius_x: float,
    radius_y: float,
    params: DotDetectionParams | None = None,
) -> list[DotCandidate]:
    """Detect red/magenta CEP17 dot candidates within the selected elliptical nucleus ROI."""

    p = params or DEFAULT_DOT_DETECTION_PARAMS
    return _detect_components(
        image_rgb,
        nucleus_x,
        nucleus_y,
        radius_x,
        radius_y,
        pixel_predicate=lambda r, g, b: _is_red_candidate_pixel(r, g, b, p),
        min_area=p.red_min_area,
        max_area=p.red_max_area,
        circularity_threshold=p.circularity_threshold,
        color_type="red",
        confidence_func=lambda pixels: _red_confidence(pixels, p),
    )


def _detect_components(
    image_rgb: Any,
    nucleus_x: float,
    nucleus_y: float,
    radius_x: float,
    radius_y: float,
    *,
    pixel_predicate,
    min_area: float,
    max_area: float,
    circularity_threshold: float,
    color_type: str,
    confidence_func,
) -> list[DotCandidate]:
    pixels, width, height = _coerce_rgb_pixels(image_rgb)
    if radius_x <= 0 or radius_y <= 0 or width <= 0 or height <= 0:
        return []

    x_min = max(0, int(math.floor(nucleus_x - radius_x)))
    x_max = min(width - 1, int(math.ceil(nucleus_x + radius_x)))
    y_min = max(0, int(math.floor(nucleus_y - radius_y)))
    y_max = min(height - 1, int(math.ceil(nucleus_y + radius_y)))

    mask: set[tuple[int, int]] = set()
    for y in range(y_min, y_max + 1):
        for x in range(x_min, x_max + 1):
            if not _inside_ellipse(x + 0.5, y + 0.5, nucleus_x, nucleus_y, radius_x, radius_y):
                continue
            if pixel_predicate(*pixels[y][x]):
                mask.add((x, y))

    candidates: list[DotCandidate] = []
    visited: set[tuple[int, int]] = set()
    for seed in list(mask):
        if seed in visited:
            continue
        component = _flood_component(seed, mask, visited)
        area = float(len(component))
        if area < min_area or area > max_area:
            continue
        circularity = _component_circularity(component, mask)
        if circularity < circularity_threshold:
            continue
        cx = sum(x + 0.5 for x, _ in component) / area
        cy = sum(y + 0.5 for _, y in component) / area
        if not _inside_ellipse(cx, cy, nucleus_x, nucleus_y, radius_x, radius_y):
            continue
        component_pixels = [pixels[y][x] for x, y in component]
        candidates.append(
            DotCandidate(
                x=float(cx),
                y=float(cy),
                area=area,
                confidence=confidence_func(component_pixels),
                color_type=color_type,
            )
        )
    candidates.sort(key=lambda c: (c.y, c.x))
    return candidates


def _coerce_rgb_pixels(image_rgb: Any) -> tuple[list[list[tuple[int, int, int]]], int, int]:
    if hasattr(image_rgb, "convert") and hasattr(image_rgb, "getdata"):
        image = image_rgb.convert("RGB")
        width, height = image.size
        access = image.load()
        return [[_as_rgb_tuple(access[x, y]) for x in range(width)] for y in range(height)], width, height
    if isinstance(image_rgb, (list, tuple)):
        rows = [list(row) for row in image_rgb]
        height = len(rows)
        width = len(rows[0]) if height else 0
        return [[_as_rgb_tuple(value) for value in row] for row in rows], width, height
    raise TypeError("image_rgb must be a Pillow image or a 2-D RGB pixel sequence")


def _as_rgb_tuple(value: Any) -> tuple[int, int, int]:
    r, g, b = value[:3]
    return int(r), int(g), int(b)


def _inside_ellipse(px: float, py: float, cx: float, cy: float, rx: float, ry: float) -> bool:
    return ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1.0


def _is_black_candidate_pixel(r: int, g: int, b: int, params: DotDetectionParams) -> bool:
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    red_chroma = r - max(g, b)
    return luminance <= params.black_threshold and max(r, g, b) <= 155 and red_chroma < 45


def _is_red_candidate_pixel(r: int, g: int, b: int, params: DotDetectionParams) -> bool:
    hue, saturation, value = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    hue_degrees = hue * 360.0
    return (
        any(start <= hue_degrees <= end for start, end in params.red_hue_range)
        and saturation >= params.red_saturation_threshold
        and value >= params.red_value_threshold
        and r > g * 1.25
        and r > b * 1.10
    )


def _flood_component(
    seed: tuple[int, int], mask: set[tuple[int, int]], visited: set[tuple[int, int]]
) -> list[tuple[int, int]]:
    stack = [seed]
    visited.add(seed)
    component: list[tuple[int, int]] = []
    while stack:
        x, y = stack.pop()
        component.append((x, y))
        for nx in (x - 1, x, x + 1):
            for ny in (y - 1, y, y + 1):
                if (nx, ny) == (x, y):
                    continue
                neighbor = (nx, ny)
                if neighbor in mask and neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
    return component


def _component_circularity(component: Iterable[tuple[int, int]], mask: set[tuple[int, int]]) -> float:
    points = list(component)
    area = len(points)
    if area == 0:
        return 0.0
    perimeter = 0
    for x, y in points:
        for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if neighbor not in mask:
                perimeter += 1
    if perimeter == 0:
        return 0.0
    return min(1.0, 4.0 * math.pi * area / (perimeter * perimeter))


def _black_confidence(pixels: list[tuple[int, int, int]], params: DotDetectionParams) -> float:
    if not pixels:
        return 0.0
    mean_luminance = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in pixels) / len(pixels)
    return max(0.0, min(1.0, (params.black_threshold - mean_luminance) / max(params.black_threshold, 1)))


def _red_confidence(pixels: list[tuple[int, int, int]], params: DotDetectionParams) -> float:
    if not pixels:
        return 0.0
    scores = []
    for r, g, b in pixels:
        _, saturation, value = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        scores.append((saturation + value) / 2.0)
    return max(0.0, min(1.0, sum(scores) / len(scores)))
