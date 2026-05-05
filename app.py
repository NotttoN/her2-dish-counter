from __future__ import annotations

import sys


def main() -> int:
    """Launch HER2-DISH Counter desktop GUI."""
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # pragma: no cover
        print("PySide6 is required. Install dependencies and retry.")
        print(f"Original error: {exc}")
        return 1

    from main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
