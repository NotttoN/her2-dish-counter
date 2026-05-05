# HER2-DISH Counter

HER2-DISH Counter is a research-use desktop application project for assisting HER2-DISH signal counting on 40x objective bright-field images.

This repository is a **Codex-ready starter repository**. It includes the project rules, initial data model, scoring logic, tests, and a Codex task file for implementing the first GUI version.

## Important disclaimer

This software is for research, education, and counting support only.

> Research-use counting support tool. Final diagnosis and interpretation must be performed by a pathologist.

It must not be used as an autonomous diagnostic device.

## Target workflow

The first version is intentionally semi-manual:

1. Open a 40x HER2-DISH image.
2. Draw ROI inside the application.
3. Click tumor nuclei manually.
4. Enter or correct HER2 black signal count and CEP17 red signal count per nucleus.
5. Add cluster correction when needed.
6. Exclude unsuitable nuclei.
7. Calculate HER2/CEP17 ratio, average HER2 copy number, and ISH Group.
8. Export JSON, CSV, and annotated PNG.

## Why v0.1 avoids full automatic nuclear segmentation

HER2-DISH images often have unclear nuclear borders, crowded nuclei, signal dots that can be mistaken for nuclei, background dust/haze, and clinically relevant cluster interpretation. Previous ImageJ/Fiji macro attempts showed that full automatic nuclear segmentation is not reliable enough as the first development target.

The first stable milestone is therefore:

> Manual tumor nucleus selection + reliable count recording + automatic scoring + reproducible export.

## Installation

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

## Run tests

```bash
python -m pytest
```

## Run the app

After Codex implements the GUI:

```bash
python -m her2dish.main
```

The starter repository already contains a minimal app shell, but the full v0.1 GUI workflow should be implemented by Codex using `codex_initial_task.md`.

## Repository contents

```text
├─ AGENTS.md                # Codex project rules and constraints
├─ codex_initial_task.md    # Initial task to paste into Codex
├─ requirements.txt         # Runtime/development dependencies
├─ pyproject.toml           # Package metadata and pytest config
├─ src/her2dish/            # Application package
├─ tests/                   # Unit tests
├─ sample_data/             # Place 40x HER2-DISH sample images here
└─ docs/                    # Development notes and future prompts
```

## Suggested Codex use

1. Upload this repository to GitHub.
2. Open the repository in Codex.
3. Paste the contents of `codex_initial_task.md` as the first task.
4. Ask Codex to implement v0.1.
5. Run tests and the app locally.
6. Feed back errors using `docs/bugfix_prompt_template.md`.

## Roadmap

### v0.1

Manual nucleus registration, manual count input, scoring, save/load, CSV export, annotated PNG export.

### v0.2

Semi-automatic black/red dot candidate detection inside manually selected nuclei.

### v0.3

PDF report, QC checklist, improved cluster workflow, and audit trail.

### v0.4

Nuclear candidate detection with user confirmation. Cellpose or other trainable models may be considered only after the manual workflow is stable.
