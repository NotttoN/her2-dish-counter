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
    red_duplicate_merge_distance_px: float = 6.0


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
    overlap_review_candidates: int = 0
    merged_duplicate_red_candidates: int = 0
    final_cep17_candidates: int = 0


@dataclass(frozen=True)
class RedDotDetectionResult:
    """CEP17 and red/black-overlap review candidates with red-mask debug counters."""

    candidates: list[DotCandidate]
    overlap_candidates: list[DotCandidate]
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
        red_duplicate_merge_distance_px=8.0,
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
        red_duplicate_merge_distance_px=6.0,
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
        red_duplicate_merge_distance_px=5.0,
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
    candidates, overlap_candidates, stats = _detect_red_components(
        image_rgb,
        nucleus_x,
        nucleus_y,
        radius_x,
        radius_y,
        p,
    )
    return RedDotDetectionResult(
        candidates=candidates,
        overlap_candidates=overlap_candidates,
        stats=stats,
        params=p,
    )


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
) -> tuple[list[DotCandidate], list[DotCandidate], ComponentDetectionStats]:
    """Detect CEP17 candidates while separating red/black overlap reviews.

    Red CEP17 candidates are intentionally semi-automatic suggestions. Large or
    low-circularity red components are treated as one CEP17 candidate by default;
    black-dominant or mixed components near HER2 black pixels are removed from
    normal red counts and, when enough red/magenta signal surrounds them, are
    returned as ``overlap_review`` display-only candidates.
    """

    pixels, width, height = _coerce_rgb_pixels(image_rgb)
    if radius_x <= 0 or radius_y <= 0 or width <= 0 or height <= 0:
        return [], [], ComponentDetectionStats()

    black_mask = _component_mask(
        pixels,
        width,
        height,
        nucleus_x,
        nucleus_y,
        radius_x,
        radius_y,
        lambda r, g, b: _is_black_candidate_pixel(r, g, b, params),
    )
    black_components = _components_from_mask(black_mask)

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

    candidates_by_component: list[tuple[int, DotCandidate]] = []
    overlap_candidates: list[DotCandidate] = []
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
        component_id = connected_components
        area = float(len(component))
        if area < params.red_min_area:
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
        metrics = _component_color_metrics(component, pixels, width, height)
        base_confidence = _red_confidence(component_pixels, params)
        confidence = max(0.0, min(1.0, base_confidence * (0.70 + 0.30 * min(1.0, circularity))))
        is_large = area >= params.red_large_min_area or area > params.red_max_area or not circularity_passed
        overlaps_black = _component_strongly_overlaps_black(component, cx, cy, black_components)
        black_dominant = metrics["black_score"] >= metrics["red_score"] * 1.15 and metrics["dark_ratio"] >= 0.25
        mixed_overlap = overlaps_black and metrics["red_ratio"] >= 0.12 and metrics["dark_ratio"] >= 0.08
        if black_dominant or mixed_overlap:
            if metrics["red_ratio"] >= 0.12:
                overlap_candidates.append(
                    DotCandidate(
                        x=float(cx),
                        y=float(cy),
                        area=area,
                        confidence=max(confidence, min(1.0, metrics["red_score"])),
                        color_type="overlap_review",
                    )
                )
            continue

        color_type = "large_red" if is_large else "red"
        if color_type == "large_red":
            large_red_candidates += 1
        candidates_by_component.append(
            (
                component_id,
                DotCandidate(
                    x=float(cx),
                    y=float(cy),
                    area=area,
                    confidence=confidence,
                    color_type=color_type,
                ),
            )
        )

    candidates, merged_duplicate_red_candidates = _merge_duplicate_red_candidates(
        candidates_by_component, params.red_duplicate_merge_distance_px
    )
    candidates.sort(key=lambda c: (c.y, c.x))
    overlap_candidates.sort(key=lambda c: (c.y, c.x))
    stats = ComponentDetectionStats(
        mask_pixels=len(mask),
        connected_components=connected_components,
        area_pass_components=area_pass_components,
        circularity_pass_components=circularity_pass_components,
        roi_pass_components=roi_pass_components,
        detected_candidates=len(candidates),
        large_red_candidates=sum(1 for candidate in candidates if candidate.color_type == "large_red"),
        overlap_review_candidates=len(overlap_candidates),
        merged_duplicate_red_candidates=merged_duplicate_red_candidates,
        final_cep17_candidates=len(candidates),
    )
    return candidates, overlap_candidates, stats


def _merge_duplicate_red_candidates(
    candidates_by_component: list[tuple[int, DotCandidate]], merge_distance_px: float
) -> tuple[list[DotCandidate], int]:
    """Merge duplicate CEP17 candidates produced from the same red component.

    The red detector is intended to emit at most one final CEP17 candidate for
    each red connected component.  This safeguard also collapses any future
    near-duplicate candidates whose centers are closer than the configured
    merge distance, preferring ordinary/large red candidates over debug-only
    overlap candidates (which are not passed into this final-count path).
    """

    if not candidates_by_component:
        return [], 0

    merged: list[tuple[set[int], DotCandidate]] = []
    for component_id, candidate in candidates_by_component:
        match_index: int | None = None
        merge_distance_sq = merge_distance_px * merge_distance_px
        for index, (component_ids, existing) in enumerate(merged):
            same_component = component_id in component_ids
            centers_close = (
                (candidate.x - existing.x) ** 2 + (candidate.y - existing.y) ** 2 <= merge_distance_sq
            )
            if same_component or centers_close:
                match_index = index
                break
        if match_index is None:
            merged.append(({component_id}, candidate))
            continue

        component_ids, existing = merged[match_index]
        component_ids.add(component_id)
        merged[match_index] = (component_ids, _combine_red_candidates(existing, candidate))

    return [candidate for _, candidate in merged], len(candidates_by_component) - len(merged)


def _combine_red_candidates(first: DotCandidate, second: DotCandidate) -> DotCandidate:
    total_area = max(1.0, float(first.area) + float(second.area))
    x = (first.x * float(first.area) + second.x * float(second.area)) / total_area
    y = (first.y * float(first.area) + second.y * float(second.area)) / total_area
    confidence_values = [value for value in (first.confidence, second.confidence) if value is not None]
    confidence = max(confidence_values) if confidence_values else None
    color_type = "large_red" if "large_red" in {first.color_type, second.color_type} else "red"
    return DotCandidate(
        x=float(x),
        y=float(y),
        area=total_area,
        confidence=confidence,
        color_type=color_type,
    )


def _components_from_mask(mask: set[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    visited: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    for seed in list(mask):
        if seed not in visited:
            components.append(_flood_component(seed, mask, visited))
    return components


def _component_strongly_overlaps_black(
    component: Iterable[tuple[int, int]],
    cx: float,
    cy: float,
    black_components: list[list[tuple[int, int]]],
) -> bool:
    points = set(component)
    if not points:
        return False
    for black_component in black_components:
        black_points = set(black_component)
        if len(black_points) < 4:
            continue
        bx, by = _component_centroid(black_points)
        black_radius = max(2.5, math.sqrt(len(black_points) / math.pi) + 1.5)
        center_near_black = (cx - bx) ** 2 + (cy - by) ** 2 <= black_radius * black_radius
        expanded_black = {
            (x + dx, y + dy)
            for x, y in black_points
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
        }
        red_border_touches_black = bool(points & expanded_black)
        if center_near_black or red_border_touches_black:
            return True
    return False


def _component_color_metrics(
    component: Iterable[tuple[int, int]],
    pixels: list[list[tuple[int, int, int]]],
    width: int,
    height: int,
) -> dict[str, float]:
    points = set(component)
    if not points:
        return {"red_ratio": 0.0, "dark_ratio": 0.0, "red_score": 0.0, "black_score": 0.0}
    sample_points = {
        (x + dx, y + dy)
        for x, y in points
        for dx in (-2, -1, 0, 1, 2)
        for dy in (-2, -1, 0, 1, 2)
        if 0 <= x + dx < width and 0 <= y + dy < height
    }
    if not sample_points:
        return {"red_ratio": 0.0, "dark_ratio": 0.0, "red_score": 0.0, "black_score": 0.0}
    red_pixels = 0
    dark_pixels = 0
    red_scores: list[float] = []
    black_scores: list[float] = []
    for x, y in sample_points:
        r, g, b = pixels[y][x]
        hue, saturation, value = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        hue_opencv = hue * 179.0
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        red_like = ((hue_opencv <= 22.0 or hue_opencv >= 125.0) and saturation >= 0.12 and value >= 0.10)
        dark_like = luminance <= 0.45 and max(r, g, b) <= 155 and (r - max(g, b)) < 45
        if red_like:
            red_pixels += 1
        if dark_like:
            dark_pixels += 1
        red_scores.append(max(0.0, saturation) * max(0.0, value) if red_like else 0.0)
        black_scores.append(max(0.0, 1.0 - luminance) if dark_like else 0.0)
    total = len(sample_points)
    return {
        "red_ratio": red_pixels / total,
        "dark_ratio": dark_pixels / total,
        "red_score": sum(red_scores) / total,
        "black_score": sum(black_scores) / total,
    }


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
    dark_enough = luminance <= params.black_threshold and max(r, g, b) <= 155
    very_dark = luminance <= params.black_threshold * 0.80 and max(r, g, b) <= 130
    return dark_enough and (red_chroma < 45 or very_dark)


def _is_red_candidate_pixel(r: int, g: int, b: int, params: DotDetectionParams) -> bool:
    if _is_black_candidate_pixel(r, g, b, params):
        return False
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
