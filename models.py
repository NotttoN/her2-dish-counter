from __future__ import annotations

import sys


def run_app() -> int:
    """Run the desktop application.

    The starter repository provides a minimal PySide6 shell. Codex should expand
    this into the full v0.1 application described in codex_initial_task.md.
    """
    try:
        from PySide6.QtWidgets import QApplication
        from .ui.main_window import MainWindow
    except Exception as exc:  # pragma: no cover - user-facing fallback
        print("Failed to import GUI dependencies.")
        print("Install dependencies with: pip install -r requirements.txt")
        print(f"Original error: {exc}")
        return 1

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
