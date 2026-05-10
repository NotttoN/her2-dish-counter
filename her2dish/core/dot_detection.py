from __future__ import annotations

from dataclasses import asdict, dataclass
import colorsys
import math
from typing import Any, Callable, Iterable


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
    """Dot detection thresholds for HER2 black and CEP17 red candidates.

    Red hue ranges use the OpenCV HSV hue scale (0-179), not degrees. Pillow
    images are coerced to RGB before HSV conversion, matching cv2.COLOR_RGB2HSV
    channel semantics if OpenCV is used by a future implementation.
    """

    black_min_area: float = 8.0
    black_max_area: float = 220.0
    black_threshold: int = 115
    red_min_area: float = 2.0
    red_max_area: float = 200.0
    red_hue_range: tuple[tuple[float, float], ...] = ((0.0, 15.0), (130.0, 179.0))
    red_saturation_threshold: float = 0.22
    red_value_threshold: float = 0.18
    circularity_threshold: float = 0.45
    red_circularity_threshold: float = 0.15
    red_large_min_area: float = 180.0
    red_peak_min_distance: float = 5.0


@dataclass(frozen=True)
class ComponentDetectionStats:
    """Debug counters for one color mask inside the selected nucleus ROI."""

    mask_pixels: int = 0
    connected_components: int = 0
    area_pass_components: int = 0
    circularity_pass_components: int = 0
    roi_pass_components: int = 0
    detected_candidates: int = 0
    large_red_candidates: int = 0


@dataclass(frozen=True)
class RedDotDetectionResult:
    """CEP17 detection candidates with red-mask debug counters."""

    candidates: list[DotCandidate]
    stats: ComponentDetectionStats
    params: DotDetectionParams


RED_SENSITIVITY_PRESETS: dict[str, DotDetectionParams] = {
    "Conservative": DotDetectionParams(
        red_min_area=4.0,
        red_max_area=260.0,
        red_hue_range=((0.0, 15.0), (140.0, 179.0)),
        red_saturation_threshold=0.35,
        red_value_threshold=0.25,
        red_circularity_threshold=0.22,
        red_large_min_area=150.0,
        red_peak_min_distance=6.0,
    ),
    "Standard": DotDetectionParams(
        red_min_area=2.0,
        red_max_area=420.0,
        red_hue_range=((0.0, 15.0), (130.0, 179.0)),
        red_saturation_threshold=0.22,
        red_value_threshold=0.18,
        red_circularity_threshold=0.08,
        red_large_min_area=180.0,
        red_peak_min_distance=5.0,
    ),
    "Sensitive": DotDetectionParams(
        red_min_area=2.0,
        red_max_area=700.0,
        red_hue_range=((0.0, 20.0), (125.0, 179.0)),
        red_saturation_threshold=0.12,
        red_value_threshold=0.12,
        red_circularity_threshold=0.02,
        red_large_min_area=100.0,
        red_peak_min_distance=4.0,
    ),
}

DEFAULT_DOT_DETECTION_PARAMS = RED_SENSITIVITY_PRESETS["Standard"]


def red_detection_params_for_preset(preset_name: str) -> DotDetectionParams:
    """Return red detection params for a UI preset name, defaulting to Standard."""

    return RED_SENSITIVITY_PRESETS.get(preset_name, DEFAULT_DOT_DETECTION_PARAMS)


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
    candidates, _ = _detect_components(
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
    return candidates


def detect_red_dots(
    image_rgb: Any,
    nucleus_x: float,
    nucleus_y: float,
    radius_x: float,
    radius_y: float,
    params: DotDetectionParams | None = None,
) -> list[DotCandidate]:
    """Detect red/magenta CEP17 dot candidates within the selected elliptical nucleus ROI."""

    return detect_red_dots_with_debug(image_rgb, nucleus_x, nucleus_y, radius_x, radius_y, params).candidates


def detect_red_dots_with_debug(
    image_rgb: Any,
    nucleus_x: float,
    nucleus_y: float,
    radius_x: float,
    radius_y: float,
    params: DotDetectionParams | None = None,
) -> RedDotDetectionResult:
    """Detect CEP17 dots and return red-mask counters for troubleshooting."""

    p = params or DEFAULT_DOT_DETECTION_PARAMS
    candidates, stats = _detect_red_components(
        image_rgb,
        nucleus_x,
        nucleus_y,
        radius_x,
        radius_y,
        p,
    )
    return RedDotDetectionResult(candidates=candidates, stats=stats, params=p)


def _detect_components(
    image_rgb: Any,
    nucleus_x: float,
    nucleus_y: float,
    radius_x: float,
    radius_y: float,
    *,
    pixel_predicate: Callable[[int, int, int], bool],
    min_area: float,
    max_area: float,
    circularity_threshold: float,
    color_type: str,
    confidence_func: Callable[[list[tuple[int, int, int]]], float],
) -> tuple[list[DotCandidate], ComponentDetectionStats]:
    pixels, width, height = _coerce_rgb_pixels(image_rgb)
    if radius_x <= 0 or radius_y <= 0 or width <= 0 or height <= 0:
        return [], ComponentDetectionStats()

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
    connected_components = 0
    area_pass_components = 0
    circularity_pass_components = 0
    roi_pass_components = 0
    for seed in list(mask):
        if seed in visited:
            continue
        component = _flood_component(seed, mask, visited)
        connected_components += 1
        area = float(len(component))
        if area < min_area or area > max_area:
            continue
        area_pass_components += 1
        circularity = _component_circularity(component, mask)
        if circularity < circularity_threshold:
            continue
        circularity_pass_components += 1
        cx = sum(x + 0.5 for x, _ in component) / area
        cy = sum(y + 0.5 for _, y in component) / area
        if not _inside_ellipse(cx, cy, nucleus_x, nucleus_y, radius_x, radius_y):
            continue
        roi_pass_components += 1
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
    stats = ComponentDetectionStats(
        mask_pixels=len(mask),
        connected_components=connected_components,
        area_pass_components=area_pass_components,
        circularity_pass_components=circularity_pass_components,
        roi_pass_components=roi_pass_components,
        detected_candidates=len(candidates),
    )
    return candidates, stats



def _detect_red_components(
    image_rgb: Any,
    nucleus_x: float,
    nucleus_y: float,
    radius_x: float,
    radius_y: float,
    params: DotDetectionParams,
) -> tuple[list[DotCandidate], ComponentDetectionStats]:
    """Detect CEP17 candidates while retaining larger/fused red components.

    Red CEP17 candidates are intentionally semi-automatic suggestions. Large or
    low-circularity components are not converted to multiple counts unless a
    simple distance-peak split finds clearly separated maxima; otherwise they are
    kept as ``large_red`` review candidates that count as one when applied.
    """

    pixels, width, height = _coerce_rgb_pixels(image_rgb)
    if radius_x <= 0 or radius_y <= 0 or width <= 0 or height <= 0:
        return [], ComponentDetectionStats()

    mask = _component_mask(
        pixels,
        width,
        height,
        nucleus_x,
        nucleus_y,
        radius_x,
        radius_y,
        lambda r, g, b: _is_red_candidate_pixel(r, g, b, params),
    )

    candidates: list[DotCandidate] = []
    visited: set[tuple[int, int]] = set()
    connected_components = 0
    area_pass_components = 0
    circularity_pass_components = 0
    roi_pass_components = 0
    large_red_candidates = 0

    for seed in list(mask):
        if seed in visited:
            continue
        component = _flood_component(seed, mask, visited)
        connected_components += 1
        area = float(len(component))
        if area < params.red_min_area or area > params.red_max_area:
            continue
        area_pass_components += 1

        circularity = _component_circularity(component, mask)
        circularity_passed = circularity >= params.red_circularity_threshold
        if circularity_passed:
            circularity_pass_components += 1

        cx, cy = _component_centroid(component)
        if not _inside_ellipse(cx, cy, nucleus_x, nucleus_y, radius_x, radius_y):
            continue
        roi_pass_components += 1

        component_pixels = [pixels[y][x] for x, y in component]
        base_confidence = _red_confidence(component_pixels, params)
        confidence = max(0.0, min(1.0, base_confidence * (0.70 + 0.30 * min(1.0, circularity))))
        is_large = area >= params.red_large_min_area or not circularity_passed

        split_peaks = _component_distance_peaks(component, params.red_peak_min_distance)
        if is_large and len(split_peaks) >= 2:
            split_area = area / len(split_peaks)
            for px, py in split_peaks:
                if _inside_ellipse(px, py, nucleus_x, nucleus_y, radius_x, radius_y):
                    candidates.append(
                        DotCandidate(
                            x=float(px),
                            y=float(py),
                            area=split_area,
                            confidence=confidence,
                            color_type="red",
                        )
                    )
            continue

        color_type = "large_red" if is_large else "red"
        if color_type == "large_red":
            large_red_candidates += 1
        candidates.append(
            DotCandidate(
                x=float(cx),
                y=float(cy),
                area=area,
                confidence=confidence,
                color_type=color_type,
            )
        )

    candidates.sort(key=lambda c: (c.y, c.x))
    stats = ComponentDetectionStats(
        mask_pixels=len(mask),
        connected_components=connected_components,
        area_pass_components=area_pass_components,
        circularity_pass_components=circularity_pass_components,
        roi_pass_components=roi_pass_components,
        detected_candidates=len(candidates),
        large_red_candidates=large_red_candidates,
    )
    return candidates, stats


def _component_mask(
    pixels: list[list[tuple[int, int, int]]],
    width: int,
    height: int,
    nucleus_x: float,
    nucleus_y: float,
    radius_x: float,
    radius_y: float,
    pixel_predicate: Callable[[int, int, int], bool],
) -> set[tuple[int, int]]:
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
    return mask


def _component_centroid(component: Iterable[tuple[int, int]]) -> tuple[float, float]:
    points = list(component)
    area = max(1, len(points))
    return (
        sum(x + 0.5 for x, _ in points) / area,
        sum(y + 0.5 for _, y in points) / area,
    )


def _component_distance_peaks(
    component: Iterable[tuple[int, int]], min_distance: float
) -> list[tuple[float, float]]:
    """Find clearly separated red-component peaks using a small distance map."""

    points = set(component)
    if len(points) < 2:
        return []
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    x_min, x_max = min(xs) - 1, max(xs) + 1
    y_min, y_max = min(ys) - 1, max(ys) + 1
    distance_scores: dict[tuple[int, int], float] = {}
    boundary = [
        (x, y)
        for y in range(y_min, y_max + 1)
        for x in range(x_min, x_max + 1)
        if (x, y) not in points
    ]
    if not boundary:
        return []
    for point in points:
        px, py = point
        distance_scores[point] = min((px - bx) ** 2 + (py - by) ** 2 for bx, by in boundary)

    local_maxima: list[tuple[float, int, int]] = []
    for x, y in points:
        score = distance_scores[(x, y)]
        if score < 4.0:
            continue
        if all(
            distance_scores.get((nx, ny), -1.0) <= score
            for nx in (x - 1, x, x + 1)
            for ny in (y - 1, y, y + 1)
            if (nx, ny) != (x, y)
        ):
            local_maxima.append((score, x, y))

    selected: list[tuple[float, float]] = []
    min_distance_sq = min_distance * min_distance
    for _, x, y in sorted(local_maxima, reverse=True):
        cx = x + 0.5
        cy = y + 0.5
        if all((cx - sx) ** 2 + (cy - sy) ** 2 >= min_distance_sq for sx, sy in selected):
            selected.append((cx, cy))
        if len(selected) >= 6:
            break
    return sorted(selected, key=lambda pt: (pt[1], pt[0]))


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
    hue_opencv = hue * 179.0
    if not any(start <= hue_opencv <= end for start, end in params.red_hue_range):
        return False
    if saturation < params.red_saturation_threshold or value < params.red_value_threshold:
        return False

    red_like = hue_opencv <= 20.0 and r >= g * 1.05 and r >= b * 0.70
    pink_magenta_like = hue_opencv >= 125.0 and r >= g * 1.03 and b >= g * 1.02
    return red_like or pink_magenta_like


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
