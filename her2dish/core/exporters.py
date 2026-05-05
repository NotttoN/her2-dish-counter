from __future__ import annotations
import csv
from pathlib import Path
from .models import CaseProject
from .scoring import calculate_score

def export_csv(project: CaseProject, path: str | Path) -> None:
    rows = project.nuclei
    with Path(path).open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["nucleus_id","x","y","her2_black","cluster_value","effective_her2","cep17_red","included","comment"])
        for n in rows:
            w.writerow([n.nucleus_id,n.x,n.y,n.her2_black,n.cluster_value,n.effective_her2,n.cep17_red,n.included,n.comment])


def export_annotated_png(project: CaseProject, path: str | Path, canvas_size: tuple[int,int]=(1200,800)) -> None:
    from PIL import Image, ImageDraw
    img = Image.new('RGB', canvas_size, 'white')
    draw = ImageDraw.Draw(img)
    for n in project.nuclei:
        color = 'green' if n.included else 'gray'
        draw.ellipse((n.x-n.radius_x,n.y-n.radius_y,n.x+n.radius_x,n.y+n.radius_y), outline=color, width=2)
        draw.text((n.x+n.radius_x+2,n.y), f"#{n.nucleus_id} H{n.effective_her2}/C{n.cep17_red}", fill='black')
    s = calculate_score(project.nuclei)
    draw.text((10,10), f"cells={s.included_cell_count} ratio={s.her2_cep17_ratio} avg={s.average_her2_copy_number} group={s.ish_group}", fill='blue')
    img.save(path)
