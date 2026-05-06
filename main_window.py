from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from her2dish.core.constants import RESEARCH_USE_DISCLAIMER
from her2dish.core.exporters import export_annotated_png, export_csv
from her2dish.core.models import CaseProject, NucleusCount, RoiRectangle
from her2dish.core.project_io import load_project, save_project
from her2dish.core.scoring import calculate_score
from image_viewer import ImageViewer

IMAGE_FILTER = "Images (*.jpg *.jpeg *.png *.tif *.tiff)"


class MainWindow(QMainWindow):
    """Main window for HER2-DISH Counter v0.1."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HER2-DISH Counter v0.1")
        self.resize(1280, 760)
        self.project = CaseProject()
        self.roi_only_mode = False
        self._updating_table = False

        self._build_menu()
        self._build_ui()
        self.update_score()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction("Open image...", self.open_image)
        file_menu.addSeparator()
        file_menu.addAction("Open JSON project...", self.open_project)
        file_menu.addAction("Save JSON project...", self.save_project_as)
        file_menu.addSeparator()
        file_menu.addAction("Export CSV...", self.export_csv_as)
        file_menu.addAction("Export annotated PNG...", self.export_png_as)

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        title = QLabel("HER2-DISH Counter v0.1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        root.addWidget(title)

        toolbar = QToolBar("Main tools", self)
        self.addToolBar(toolbar)
        toolbar.addAction("Open image", self.open_image)
        toolbar.addAction("Pan", lambda: self.viewer.set_mode(ImageViewer.MODE_PAN))
        toolbar.addAction("Add nucleus", lambda: self.viewer.set_mode(ImageViewer.MODE_ADD_NUCLEUS))
        toolbar.addAction("Rect ROI", lambda: self.viewer.set_mode(ImageViewer.MODE_RECT_ROI))
        toolbar.addAction("ROI-only ON/OFF", self.toggle_roi_only)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(splitter, stretch=1)

        self.viewer = ImageViewer(self)
        self.viewer.nucleusClicked.connect(self.add_nucleus_at)
        self.viewer.roiChanged.connect(self.set_roi)
        self.viewer.statusChanged.connect(self.statusBar().showMessage)
        splitter.addWidget(self.viewer)

        right_panel = QWidget(self)
        right = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([760, 520])

        self.table = QTableWidget(0, 10, self)
        self.table.setHorizontalHeaderLabels(
            ["ID", "X", "Y", "HER2", "CEP17", "Cluster", "Effective HER2", "Included", "Comment", "Radius"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._table_item_changed)
        right.addWidget(self.table)

        controls = QHBoxLayout()
        add_btn = QPushButton("Add nucleus")
        add_btn.clicked.connect(lambda: self.add_nucleus_at(0, 0))
        controls.addWidget(add_btn)

        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self.remove_selected_rows)
        controls.addWidget(remove_btn)

        self.roi_mode_label = QLabel("ROI-only: off")
        controls.addWidget(self.roi_mode_label)
        controls.addStretch(1)
        right.addLayout(controls)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        right.addWidget(self.summary_label)

        disclaimer = QLabel(RESEARCH_USE_DISCLAIMER)
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("color: #666;")
        right.addWidget(disclaimer)

    def _make_spin(self, minimum: int = 0, maximum: int = 999, value: int = 0, on_change: Callable | None = None) -> QSpinBox:
        spin = QSpinBox(self)
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        if on_change is not None:
            spin.valueChanged.connect(on_change)
        return spin

    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open image", "", IMAGE_FILTER)
        if not path:
            return
        try:
            self.viewer.load_image(path)
        except ValueError as exc:
            QMessageBox.critical(self, "Open image failed", str(exc))
            return
        self.project.image_path = path
        self.viewer.set_roi(self.project.roi)
        self.viewer.draw_nuclei(self.project.nuclei)

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open JSON project", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.project = load_project(path)
        except Exception as exc:  # pragma: no cover - user-facing file error
            QMessageBox.critical(self, "Open project failed", str(exc))
            return
        if self.project.image_path and Path(self.project.image_path).exists():
            try:
                self.viewer.load_image(self.project.image_path)
            except ValueError:
                pass
        self.refresh_table_from_project()
        self.viewer.set_roi(self.project.roi)
        self.viewer.draw_nuclei(self.project.nuclei)
        self.update_score()

    def save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save JSON project", "her2-dish-project.json", "JSON (*.json)")
        if path:
            save_project(self.project, path)

    def export_csv_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "her2-dish-counts.csv", "CSV (*.csv)")
        if path:
            export_csv(self.project, path)

    def export_png_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export annotated PNG", "her2-dish-annotated.png", "PNG (*.png)")
        if not path:
            return
        try:
            export_annotated_png(self.project, path)
        except Exception as exc:  # pragma: no cover - optional Pillow/runtime file errors
            QMessageBox.critical(self, "Export PNG failed", str(exc))

    def toggle_roi_only(self) -> None:
        self.roi_only_mode = not self.roi_only_mode
        self.roi_mode_label.setText(f"ROI-only: {'on' if self.roi_only_mode else 'off'}")

    def set_roi(self, roi: RoiRectangle) -> None:
        self.project.roi = roi.normalized()
        self.viewer.set_roi(self.project.roi)

    def add_nucleus_at(self, x: float, y: float) -> None:
        if self.roi_only_mode and self.project.roi is not None and not self.project.roi.contains(x, y):
            self.statusBar().showMessage("Click ignored: outside ROI")
            return
        nucleus = NucleusCount(nucleus_id=len(self.project.nuclei) + 1, x=float(x), y=float(y))
        self.project.nuclei.append(nucleus)
        self._append_row(nucleus)
        self.viewer.draw_nuclei(self.project.nuclei)
        self.update_score()

    def _append_row(self, nucleus: NucleusCount) -> None:
        self._updating_table = True
        row = self.table.rowCount()
        self.table.insertRow(row)

        for col, value, editable in [
            (0, str(nucleus.nucleus_id), False),
            (1, f"{nucleus.x:.1f}", False),
            (2, f"{nucleus.y:.1f}", False),
            (6, str(nucleus.effective_her2), False),
            (8, nucleus.comment, True),
            (9, f"{nucleus.radius_x:.1f} × {nucleus.radius_y:.1f}", False),
        ]:
            item = QTableWidgetItem(value)
            if not editable:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, col, item)

        her2 = self._make_spin(value=nucleus.her2_black, on_change=self._sync_project_from_table)
        cep17 = self._make_spin(value=nucleus.cep17_red, on_change=self._sync_project_from_table)
        cluster = self._make_spin(value=nucleus.cluster_value, on_change=self._sync_project_from_table)
        included = QCheckBox()
        included.setChecked(nucleus.included)
        included.stateChanged.connect(self._sync_project_from_table)

        self.table.setCellWidget(row, 3, her2)
        self.table.setCellWidget(row, 4, cep17)
        self.table.setCellWidget(row, 5, cluster)
        self.table.setCellWidget(row, 7, included)
        self._updating_table = False

    def refresh_table_from_project(self) -> None:
        self._updating_table = True
        self.table.setRowCount(0)
        self._updating_table = False
        for index, nucleus in enumerate(self.project.nuclei, start=1):
            nucleus.nucleus_id = index
            self._append_row(nucleus)

    def remove_selected_rows(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self.project.nuclei):
                del self.project.nuclei[row]
        for index, nucleus in enumerate(self.project.nuclei, start=1):
            nucleus.nucleus_id = index
        self.refresh_table_from_project()
        self.viewer.draw_nuclei(self.project.nuclei)
        self.update_score()

    def _table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_table:
            return
        if item.column() == 8 and item.row() < len(self.project.nuclei):
            self.project.nuclei[item.row()].comment = item.text()
            self.update_score()

    def _sync_project_from_table(self) -> None:
        if self._updating_table:
            return
        for row, nucleus in enumerate(self.project.nuclei):
            her2 = self.table.cellWidget(row, 3)
            cep17 = self.table.cellWidget(row, 4)
            cluster = self.table.cellWidget(row, 5)
            included = self.table.cellWidget(row, 7)
            if isinstance(her2, QSpinBox):
                nucleus.her2_black = her2.value()
            if isinstance(cep17, QSpinBox):
                nucleus.cep17_red = cep17.value()
            if isinstance(cluster, QSpinBox):
                nucleus.cluster_value = cluster.value()
            if isinstance(included, QCheckBox):
                nucleus.included = included.isChecked()
            effective_item = self.table.item(row, 6)
            if effective_item is not None:
                effective_item.setText(str(nucleus.effective_her2))
        self.viewer.draw_nuclei(self.project.nuclei)
        self.update_score()

    def update_score(self) -> None:
        result = calculate_score(self.project.nuclei)
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
