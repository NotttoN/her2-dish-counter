from __future__ import annotations

import csv
from pathlib import Path

from .constants import RESEARCH_USE_DISCLAIMER
from .models import CaseProject, NucleusCount
from .scoring import ScoreResult, calculate_score


def export_csv(project: CaseProject, path: str | Path) -> None:
    rows = project.nuclei
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "nucleus_id",
                "x",
                "y",
                "radius_x",
                "radius_y",
                "her2_black",
                "small_cluster_count",
                "large_cluster_count",
                "manual_cluster_add",
                "effective_her2",
                "cep17_red",
                "included",
                "comment",
            ]
        )
        for n in rows:
            w.writerow(
                [
                    n.nucleus_id,
                    n.x,
                    n.y,
                    n.radius_x,
                    n.radius_y,
                    n.her2_black,
                    n.small_cluster_count,
                    n.large_cluster_count,
                    n.manual_cluster_add,
                    n.effective_her2,
                    n.cep17_red,
                    n.included,
                    n.comment,
                ]
            )


def score_summary_lines(score: ScoreResult) -> list[str]:
    ratio = f"{score.her2_cep17_ratio:.3f}" if score.her2_cep17_ratio is not None else "N/A"
    avg = f"{score.average_her2_copy_number:.3f}" if score.average_her2_copy_number is not None else "N/A"
    return [
        f"Included nuclei: {score.included_cell_count}",
        f"Total HER2 (effective): {score.total_her2}",
        f"Total CEP17: {score.total_cep17}",
        f"HER2/CEP17 ratio: {ratio}",
        f"Average HER2 copy number: {avg}",
        f"ISH group: {score.ish_group}",
    ]


def _open_base_image(project: CaseProject, canvas_size: tuple[int, int]):
    from PIL import Image

    if project.image_path and Path(project.image_path).exists():
        return Image.open(project.image_path).convert("RGB")
    return Image.new("RGB", canvas_size, "white")


def _text_size(draw, text: str, font=None) -> tuple[int, int]:
    """Return the rendered width/height for Pillow default-font text."""

    bbox = draw.textbbox((0, 0), text, font=font)
    return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])


def _wrap_text(draw, text: str, max_width: int, font=None) -> list[str]:
    """Word-wrap text so every line fits within max_width pixels."""

    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if _text_size(draw, candidate, font)[0] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = word
        else:
            lines.append(word)
            current = ""
    if current:
        lines.append(current)
    return lines


def _draw_label_box(
    draw,
    xy: tuple[float, float],
    text: str,
    *,
    fill: str,
    box_fill: tuple[int, int, int] = (255, 255, 255),
    outline: str = "navy",
    bounds: tuple[float, float, float, float] | None = None,
) -> None:
    """Draw readable annotation text on a small high-contrast background."""

    padding_x = 4
    padding_y = 2
    text_w, text_h = _text_size(draw, text)
    x, y = xy
    if bounds is not None:
        min_x, min_y, max_x, max_y = bounds
        x = min(max(x, min_x), max_x - text_w - 2 * padding_x)
        y = min(max(y, min_y), max_y - text_h - 2 * padding_y)
    box = (x, y, x + text_w + 2 * padding_x, y + text_h + 2 * padding_y)
    draw.rectangle(box, fill=box_fill, outline=outline)
    draw.text((x + padding_x, y + padding_y), text, fill=fill)


def _draw_nucleus(draw, nucleus: NucleusCount, offset: tuple[int, int], bounds: tuple[int, int, int, int]) -> None:
    color = "lime" if nucleus.included else "gray"
    text_color = "black" if nucleus.included else "dimgray"
    outline = "green" if nucleus.included else "dimgray"
    ox, oy = offset
    x, y = nucleus.x + ox, nucleus.y + oy
    draw.ellipse(
        (x - nucleus.radius_x, y - nucleus.radius_y, x + nucleus.radius_x, y + nucleus.radius_y),
        outline=color,
        width=3,
    )
    label_x = x + nucleus.radius_x + 6
    label_y = y - nucleus.radius_y
    _draw_label_box(draw, (label_x, label_y), f"#{nucleus.nucleus_id}", fill=text_color, outline=outline, bounds=bounds)
    _draw_label_box(
        draw,
        (label_x, label_y + 20),
        f"H{nucleus.effective_her2}/C{nucleus.cep17_red}",
        fill=text_color,
        outline=outline,
        bounds=bounds,
    )


def _draw_summary_panel(draw, panel_box: tuple[int, int, int, int], score: ScoreResult) -> None:
    panel_left, panel_top, panel_right, panel_bottom = panel_box
    panel_padding = 18
    line_gap = 6
    title = "HER2-DISH Counter v0.1.4"
    summary_lines = score_summary_lines(score)
    max_text_width = panel_right - panel_left - 2 * panel_padding

    disclaimer_lines = _wrap_text(draw, RESEARCH_USE_DISCLAIMER, max_text_width)
    panel_lines = [title, *summary_lines, *disclaimer_lines]
    line_height = max(_text_size(draw, line)[1] for line in panel_lines) + line_gap

    draw.rectangle(panel_box, fill=(255, 255, 255), outline="navy", width=2)
    y = panel_top + panel_padding
    for i, line in enumerate(panel_lines):
        if i == 0:
            fill = "navy"
        elif i >= 1 + len(summary_lines):
            fill = "dimgray"
        else:
            fill = "black"
        draw.text((panel_left + panel_padding, y), line, fill=fill)
        y += line_height
        if i == 0:
            y += 4


def _summary_panel_height(draw, width: int, score: ScoreResult) -> int:
    panel_padding = 18
    line_gap = 6
    max_text_width = width - 2 * panel_padding
    panel_lines = ["HER2-DISH Counter v0.1.4", *score_summary_lines(score)]
    panel_lines.extend(_wrap_text(draw, RESEARCH_USE_DISCLAIMER, max_text_width))
    line_height = max(_text_size(draw, line)[1] for line in panel_lines) + line_gap
    title_spacing = 4
    return 2 * panel_padding + line_height * len(panel_lines) + title_spacing


def export_annotated_png(project: CaseProject, path: str | Path, canvas_size: tuple[int, int] = (1200, 800)) -> None:
    """Export original image plus ROI, nucleus annotations, counts, summary, and disclaimer."""

    from PIL import Image, ImageDraw

    base_img = _open_base_image(project, canvas_size)
    score = calculate_score(project.nuclei)

    # Expand the exported canvas instead of painting the summary over the source image.
    # This preserves nuclei near the image bottom and gives edge annotations room to breathe.
    image_padding = 28
    panel_gap = 14
    scratch = Image.new("RGB", (1, 1), "white")
    scratch_draw = ImageDraw.Draw(scratch)
    longest_required_line = max(
        ["HER2-DISH Counter v0.1.4", *score_summary_lines(score), RESEARCH_USE_DISCLAIMER],
        key=lambda line: _text_size(scratch_draw, line)[0],
    )
    min_panel_width = _text_size(scratch_draw, longest_required_line)[0] + 36
    output_width = max(base_img.width + 2 * image_padding, min_panel_width)
    panel_height = _summary_panel_height(scratch_draw, output_width, score)
    output_height = base_img.height + 2 * image_padding + panel_gap + panel_height

    img = Image.new("RGB", (output_width, output_height), "white")
    image_left = image_padding
    image_top = image_padding
    img.paste(base_img, (image_left, image_top))
    draw = ImageDraw.Draw(img)

    image_bounds = (0, 0, output_width, image_top + base_img.height + image_padding)
    draw.rectangle(
        (image_left, image_top, image_left + base_img.width, image_top + base_img.height),
        outline=(180, 180, 180),
        width=1,
    )

    if project.roi is not None:
        roi = project.roi.normalized()
        roi_box = (
            image_left + roi.x,
            image_top + roi.y,
            image_left + roi.x2,
            image_top + roi.y2,
        )
        draw.rectangle(roi_box, outline="yellow", width=4)
        _draw_label_box(
            draw,
            (image_left + roi.x + 4, max(0, image_top + roi.y - 22)),
            roi.name,
            fill="black",
            outline="goldenrod",
            bounds=image_bounds,
        )

    for nucleus in project.nuclei:
        _draw_nucleus(draw, nucleus, (image_left, image_top), image_bounds)

    panel_top = base_img.height + 2 * image_padding + panel_gap
    _draw_summary_panel(draw, (0, panel_top, output_width - 1, output_height - 1), score)

    img.save(path)
