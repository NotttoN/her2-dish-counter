from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from her2dish.core.constants import RESEARCH_USE_DISCLAIMER
from her2dish.core.models import NucleusCount
from her2dish.core.scoring import calculate_score


class MainWindow(QMainWindow):
    """Main window for HER2-DISH Counter v0.1."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HER2-DISH Counter v0.1")
        self.resize(980, 680)

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        title = QLabel("HER2-DISH Counter v0.1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        root.addWidget(title)

        self.table = QTableWidget(0, 7, self)
        self.table.setHorizontalHeaderLabels(
            ["ID", "HER2", "CEP17", "Cluster", "Effective HER2", "Included", "Comment"]
        )
        self.table.verticalHeader().setVisible(False)
        root.addWidget(self.table)

        controls = QHBoxLayout()
        add_btn = QPushButton("Add nucleus")
        add_btn.clicked.connect(self.add_row)
        controls.addWidget(add_btn)

        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self.remove_selected_rows)
        controls.addWidget(remove_btn)
        controls.addStretch(1)
        root.addLayout(controls)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        disclaimer = QLabel(RESEARCH_USE_DISCLAIMER)
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("color: #666;")
        root.addWidget(disclaimer)

        for _ in range(5):
            self.add_row()
        self.update_score()

    def _make_spin(self, minimum: int = 0, maximum: int = 999, value: int = 0, on_change: Callable | None = None) -> QSpinBox:
        spin = QSpinBox(self)
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        if on_change is not None:
            spin.valueChanged.connect(on_change)
        return spin

    def add_row(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        id_item = QTableWidgetItem(str(row + 1))
        id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, id_item)

        her2 = self._make_spin(on_change=self.update_score)
        cep17 = self._make_spin(on_change=self.update_score)
        cluster = self._make_spin(on_change=self.update_score)
        effective = QLabel("0")
        effective.setAlignment(Qt.AlignmentFlag.AlignCenter)
        included = QCheckBox()
        included.setChecked(True)
        included.stateChanged.connect(self.update_score)
        comment = QTableWidgetItem("")

        self.table.setCellWidget(row, 1, her2)
        self.table.setCellWidget(row, 2, cep17)
        self.table.setCellWidget(row, 3, cluster)
        self.table.setCellWidget(row, 4, effective)
        self.table.setCellWidget(row, 5, included)
        self.table.setItem(row, 6, comment)

        self.update_score()

    def remove_selected_rows(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setText(str(row + 1))
        self.update_score()

    def _collect_nuclei(self) -> list[NucleusCount]:
        nuclei: list[NucleusCount] = []
        for row in range(self.table.rowCount()):
            her2 = self.table.cellWidget(row, 1)
            cep17 = self.table.cellWidget(row, 2)
            cluster = self.table.cellWidget(row, 3)
            included = self.table.cellWidget(row, 5)
            comment_item = self.table.item(row, 6)

            if not isinstance(her2, QSpinBox) or not isinstance(cep17, QSpinBox) or not isinstance(cluster, QSpinBox) or not isinstance(included, QCheckBox):
                continue

            nuclei.append(
                NucleusCount(
                    nucleus_id=row + 1,
                    x=0,
                    y=0,
                    her2_black=her2.value(),
                    cep17_red=cep17.value(),
                    cluster_value=cluster.value(),
                    included=included.isChecked(),
                    comment=comment_item.text() if comment_item else "",
                )
            )
        return nuclei

    def update_score(self) -> None:
        nuclei = self._collect_nuclei()

        for row, nucleus in enumerate(nuclei):
            widget = self.table.cellWidget(row, 4)
            if isinstance(widget, QLabel):
                widget.setText(str(nucleus.effective_her2))

        result = calculate_score(nuclei)
        ratio = f"{result.her2_cep17_ratio:.3f}" if result.her2_cep17_ratio is not None else "N/A"
        avg = f"{result.average_her2_copy_number:.3f}" if result.average_her2_copy_number is not None else "N/A"
        warnings = "\n".join(f"• {w}" for w in result.warnings) if result.warnings else "None"

        self.summary_label.setText(
            "\n".join(
                [
                    f"Included nuclei: {result.included_cell_count}",
                    f"Total HER2 (effective): {result.total_her2}",
                    f"Total CEP17: {result.total_cep17}",
                    f"HER2/CEP17 ratio: {ratio}",
                    f"Average HER2 copy number: {avg}",
                    f"ISH group: {result.ish_group}",
                    f"Warnings: {warnings}",
                ]
            )
        )
