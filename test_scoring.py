from __future__ import annotations

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel, QMainWindow, QTextEdit, QVBoxLayout, QWidget
except Exception:  # pragma: no cover
    Qt = None
    QLabel = QMainWindow = QTextEdit = QVBoxLayout = QWidget = object

from her2dish.core.constants import RESEARCH_USE_DISCLAIMER


class MainWindow(QMainWindow):
    """Minimal starter shell.

    Codex should replace/expand this with the full v0.1 GUI.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HER2-DISH Counter v0.1 starter")
        self.resize(1100, 760)

        central = QWidget()
        layout = QVBoxLayout(central)
        title = QLabel("HER2-DISH Counter")
        if Qt is not None:
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setPlainText(
            "This is a Codex-ready starter shell.\n\n"
            "Ask Codex to implement v0.1 using codex_initial_task.md.\n\n"
            f"{RESEARCH_USE_DISCLAIMER}"
        )
        layout.addWidget(instructions)
        self.setCentralWidget(central)
