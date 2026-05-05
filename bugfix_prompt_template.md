# Codex initial task: implement HER2-DISH Counter v0.1

Please implement HER2-DISH Counter v0.1 in this repository.

Read `AGENTS.md` first and strictly follow its project rules, constraints, and research-use disclaimer.

## Background

This app targets bright-field HER2-DISH images captured using a 40x objective lens.

Previous ImageJ/Fiji macro attempts had unstable nuclear segmentation due to crowded nuclei, unclear nuclear borders, black/red DISH signals being mistaken for nuclei, and background artifacts. Therefore, v0.1 must not attempt full automatic nuclear segmentation.

The purpose of v0.1 is to provide a stable manual/semi-manual counting support workflow:

- The user opens a 40x HER2-DISH image.
- The user draws ROI in the app.
- The user clicks tumor nuclei manually.
- The user enters HER2 black signal counts and CEP17 red signal counts for each nucleus.
- The app calculates HER2/CEP17 ratio, average HER2 copy number, and ASCO/CAP dual-probe ISH Group 1-5.
- The app saves JSON and exports CSV and annotated PNG.

## Required implementation

### 1. Basic GUI

Use PySide6.

Create a main window with:

- Menu bar:
  - Open Image
  - Save Project
  - Load Project
  - Export CSV
  - Export Annotated PNG
  - Exit
- Toolbar:
  - Select
  - Draw ROI
  - Add Nucleus
  - Delete Nucleus
  - Toggle Included
- Central image viewer.
- Right panel with case metadata, nucleus table, calculation summary, and warnings.
- Status bar showing image coordinates, zoom level, and messages.

### 2. Image loading and viewing

Support:

- jpg
- jpeg
- png
- tif
- tiff

Implement:

- Image display.
- Zoom.
- Pan.
- Correct screen-to-image coordinate conversion.
- Overlays that remain correctly aligned during zoom and pan.

### 3. ROI

At minimum, implement rectangular ROI drawing.

Preferred if feasible:

- Polygon ROI.

ROI requirements:

- Show ROI as overlay.
- Store ROI coordinates in image coordinates.
- Save/load ROI in project JSON.

### 4. Nucleus registration

Implement Add Nucleus mode.

When user clicks the image:

- Add one nucleus at the clicked image coordinate.
- Assign a unique nucleus_id.
- Display a circle/ellipse around the nucleus.
- Display nucleus_id next to the nucleus.
- Add the nucleus to the right-side table.

Also implement:

- Select nucleus from image or table.
- Delete selected nucleus.
- Toggle included/excluded.
- Preserve image-coordinate consistency.

### 5. Nucleus table

Create an editable table with columns:

- nucleus_id
- included
- x
- y
- HER2 black
- CEP17 red
- cluster value
- cluster note
- comment

Editable columns:

- included
- HER2 black
- CEP17 red
- cluster value
- cluster note
- comment

On edit, update calculation immediately.

### 6. Calculation

Use the existing scoring module as the single source of truth.

Included nuclei only.

For each included nucleus:

```text
effective_her2 = her2_black + cluster_value
```

Calculate:

- included_cell_count
- total_her2
- total_cep17
- her2_cep17_ratio
- average_her2_copy_number
- ASCO/CAP dual-probe ISH Group 1-5
- warnings

If total CEP17 is 0, result is Not evaluable.

### 7. Warnings

Display warnings for:

- Borderline ratio 1.8 to 2.2 inclusive: recommend additional 20 nuclei according to laboratory workflow.
- Group 2-4: requires IHC correlation and/or pathologist review according to the laboratory workflow.
- Fewer than 20 included nuclei: indicate that at least 20 nuclei are generally needed for the initial count.
- 20 included nuclei reached: display milestone message.

All windows and exports must include:

```text
Research-use counting support tool. Final diagnosis and interpretation must be performed by a pathologist.
```

### 8. JSON save/load

Save project JSON containing:

- case_id
- specimen_id
- operator
- image_path
- ihc_score
- notes
- rois
- nuclei

Load project JSON and restore:

- image if available
- ROI overlays
- nuclei overlays
- table
- calculation summary

### 9. CSV export

Export one row per nucleus with:

- case_id
- specimen_id
- image_path
- operator
- nucleus_id
- x
- y
- included
- her2_black
- cep17_red
- cluster_value
- cluster_note
- effective_her2
- comment

Also export a summary CSV or summary section containing:

- included_cell_count
- total_her2
- total_cep17
- her2_cep17_ratio
- average_her2_copy_number
- ish_group
- warning_messages

### 10. Annotated PNG export

Export a new PNG with:

- Original image background.
- ROI outline.
- Nucleus circles/ellipses.
- Nucleus IDs.
- Included/excluded distinction.
- HER2/CEP17 count text near each nucleus if feasible.
- Summary in a corner.
- Research-use disclaimer.

Do not overwrite the original image.

### 11. Tests

Keep and extend tests as needed.

At minimum, ensure:

```bash
python -m pytest
```

passes.

Add tests for any changed scoring or project I/O behavior.

### 12. Documentation

Update README.md with:

- Installation
- Run command
- Basic workflow
- Export instructions
- Test instructions
- Known limitations
- v0.2 roadmap

## Important constraints

- Do not implement full automatic nuclear segmentation in v0.1.
- Do not add Cellpose, StarDist, SAM, PyTorch, or other heavy AI dependencies.
- Do not claim clinical diagnostic approval.
- Do not overwrite original images.
- Keep scoring logic independent from GUI code.
- Keep code modular and testable.

## Final report requested from Codex

After implementation, report:

1. Implemented features.
2. Files created or modified.
3. Test results.
4. Known limitations.
5. Recommended next steps for v0.2.
