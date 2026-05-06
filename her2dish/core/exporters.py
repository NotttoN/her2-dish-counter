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
                "cluster_value",
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
                    n.cluster_value,
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


def _draw_nucleus(draw, nucleus: NucleusCount) -> None:
    color = "lime" if nucleus.included else "gray"
    text_color = "black" if nucleus.included else "dimgray"
    x, y = nucleus.x, nucleus.y
    draw.ellipse(
        (x - nucleus.radius_x, y - nucleus.radius_y, x + nucleus.radius_x, y + nucleus.radius_y),
        outline=color,
        width=3,
    )
    draw.text((x + nucleus.radius_x + 3, y - nucleus.radius_y), f"#{nucleus.nucleus_id}", fill=text_color)
    draw.text((x + nucleus.radius_x + 3, y + 2), f"H{nucleus.effective_her2}/C{nucleus.cep17_red}", fill=text_color)


def export_annotated_png(project: CaseProject, path: str | Path, canvas_size: tuple[int, int] = (1200, 800)) -> None:
    """Export original image plus ROI, nucleus annotations, counts, summary, and disclaimer."""

    from PIL import ImageDraw

    img = _open_base_image(project, canvas_size)
    draw = ImageDraw.Draw(img)

    if project.roi is not None:
        roi = project.roi.normalized()
        draw.rectangle((roi.x, roi.y, roi.x2, roi.y2), outline="yellow", width=4)
        draw.text((roi.x + 4, max(0, roi.y - 16)), roi.name, fill="yellow")

    for nucleus in project.nuclei:
        _draw_nucleus(draw, nucleus)

    score = calculate_score(project.nuclei)
    panel_lines = ["HER2-DISH Counter v0.1", *score_summary_lines(score), RESEARCH_USE_DISCLAIMER]
    line_height = 16
    panel_height = line_height * len(panel_lines) + 16
    panel_top = max(0, img.height - panel_height)
    draw.rectangle((0, panel_top, img.width, img.height), fill=(255, 255, 255), outline="navy")
    for i, line in enumerate(panel_lines):
        draw.text((10, panel_top + 8 + i * line_height), line, fill="navy" if i == 0 else "black")

    img.save(path)
