# HER2-DISH Counter v0.1.2

HER2-DISH Counter is a research-use desktop helper for manual HER2 dual-probe ISH counting. It is not an automated segmentation or diagnostic system. Final diagnostic interpretation must be performed by a pathologist.

## Install and start

```bash
python -m pip install -r requirements.txt
python app.py
```

The application starts a PySide6 window with an image viewer, a nucleus count table, and a live HER2/CEP17 calculation panel.

## Open an image

1. Choose **File → Open image...** or click **Open image** on the toolbar.
2. Select a supported image file: `jpg`, `jpeg`, `png`, `tif`, or `tiff`.
3. The image appears in the viewer. Use the mouse wheel to zoom and **Pan** mode to drag the view.

## Create a rectangular ROI

1. Click **Rect ROI** on the toolbar.
2. Drag on the image to draw a rectangular tumor ROI.
3. The ROI is shown as a yellow rectangle and is saved into the JSON project.
4. Click **ROI-only ON/OFF** to restrict nucleus registration to clicks inside the ROI.

## Register nuclei by clicking

1. Open an image.
2. Click **Add nucleus** on the toolbar.
3. Click each nucleus on the image.
4. A new nucleus row is added to the table with image-coordinate `x` and `y` values, default ellipse radii, zero signal counts, and `Included` enabled.
5. Each registered nucleus is drawn on the image with its nucleus number, an ellipse, and `H/C` count text. Included nuclei are green; excluded nuclei are gray.

The **Add nucleus** button below the table also enters image-click registration mode; no nucleus row is created until you click inside the displayed image.

## Enter counts and comments

Edit the table columns directly:

- **HER2**: black HER2 signal count.
- **CEP17**: red CEP17 signal count.
- **Cluster**: additional HER2 cluster value added to HER2.
- **Included**: whether the nucleus contributes to the score.
- **Comment**: free text note.

The **Effective HER2**, totals, HER2/CEP17 ratio, average HER2 copy number, ISH group, and warnings update immediately after edits.

## Save, load, and export

Use the **File** menu:

- **Save JSON project...** writes image path, ROI coordinates, nucleus coordinates, radii, counts, included flags, and comments.
- **Open JSON project...** restores saved project data and reloads the referenced image when available.
- **Export CSV...** writes a count table with coordinates, radii, raw counts, effective HER2, inclusion status, and comments.
- **Export annotated PNG...** writes an annotated image containing the original image, ROI, nucleus numbers, ellipses, HER2/CEP17 counts, summary score, and the research-use/pathologist-review disclaimer.

## Scope of v0.1.2

- Nuclei are manually registered by user clicks.
- Fully automated nucleus segmentation is intentionally not implemented in v0.1.2.
- Scoring, project I/O, and exporters live in `her2dish/core` so calculation logic remains separate from the GUI.
