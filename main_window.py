from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from PIL import Image

from her2dish.core.constants import RESEARCH_USE_DISCLAIMER
from her2dish.core.dot_detection import (
    RED_SENSITIVITY_PRESETS,
    ComponentDetectionStats,
    DotDetectionParams,
    detect_black_cluster_candidates,
    detect_black_dots,
    detect_red_dots_with_debug,
    params_from_sliders,
)
from her2dish.core.exporters import export_annotated_png, export_csv
from her2dish.core.models import CaseProject, DetectionSettings, NucleusCount, RoiRectangle
from her2dish.core.project_io import load_project, save_project
from her2dish.core.scoring import calculate_score
from image_viewer import ImageViewer

IMAGE_FILTER = "Images (*.jpg *.jpeg *.png *.tif *.tiff)"

COL_ID = 0
COL_X = 1
COL_Y = 2
COL_RADIUS_X = 3
COL_RADIUS_Y = 4
COL_HER2 = 5
COL_SMALL_CLUSTER = 6
COL_LARGE_CLUSTER = 7
COL_MANUAL_ADD = 8
COL_EFFECTIVE_HER2 = 9
COL_CEP17 = 10
COL_INCLUDED = 11
COL_COMMENT = 12

TABLE_HEADERS = [
    "ID",
    "X",
    "Y",
    "Rx",
    "Ry",
    "HER2",
    "S-cluster",
    "L-cluster",
    "Manual +",
    "Eff. HER2",
    "CEP17",
    "Inc.",
    "Comment",
]

TABLE_COLUMN_WIDTHS = {
    COL_ID: 45,
    COL_X: 70,
    COL_Y: 70,
    COL_RADIUS_X: 55,
    COL_RADIUS_Y: 55,
    COL_HER2: 75,
    COL_SMALL_CLUSTER: 85,
    COL_LARGE_CLUSTER: 85,
    COL_MANUAL_ADD: 90,
    COL_EFFECTIVE_HER2: 85,
    COL_CEP17: 75,
    COL_INCLUDED: 55,
    COL_COMMENT: 160,
}


class MainWindow(QMainWindow):
    """Main window for HER2-DISH Counter v0.2.7."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HER2-DISH Counter v0.2.7")
        self.resize(1280, 760)
        self.project = CaseProject()
        self.roi_only_mode = False
        self._updating_table = False
        self.selected_nucleus_id: int | None = None
        self.last_red_detection_stats: ComponentDetectionStats | None = None
        self.last_red_detection_nucleus_id: int | None = None
        self.last_detection_params: DotDetectionParams | None = None
        self._applying_detection_preset = False

        self._build_menu()
        self._build_ui()
        self._build_shortcuts()
        self.update_selected_nucleus_panel()
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

        title = QLabel("HER2-DISH Counter v0.2.7")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        root.addWidget(title)

        toolbar = QToolBar("Main tools", self)
        self.addToolBar(toolbar)
        toolbar.addAction("Open image", self.open_image)
        toolbar.addAction("Pan", lambda: self.viewer.set_mode(ImageViewer.MODE_PAN))
        toolbar.addAction("Select/Edit", lambda: self.viewer.set_mode(ImageViewer.MODE_SELECT_EDIT))
        toolbar.addAction("Add nucleus", lambda: self.viewer.set_mode(ImageViewer.MODE_ADD_NUCLEUS))
        toolbar.addAction("Rect ROI", lambda: self.viewer.set_mode(ImageViewer.MODE_RECT_ROI))
        toolbar.addAction("ROI-only ON/OFF", self.toggle_roi_only)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(splitter, stretch=1)

        self.viewer = ImageViewer(self)
        self.viewer.nucleusClicked.connect(self.add_nucleus_at)
        self.viewer.nucleusSelected.connect(self.select_nucleus_by_id)
        self.viewer.nucleusRoiChanged.connect(self.update_nucleus_roi)
        self.viewer.roiChanged.connect(self.set_roi)
        self.viewer.statusChanged.connect(self.statusBar().showMessage)
        splitter.addWidget(self.viewer)

        right_panel = QWidget(self)
        right = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([760, 520])

        self.table = QTableWidget(0, len(TABLE_HEADERS), self)
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)
        self._apply_count_table_column_widths()
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemChanged.connect(self._table_item_changed)
        self.table.itemSelectionChanged.connect(self._table_selection_changed)
        right.addWidget(self.table)

        controls = QHBoxLayout()
        self.add_nucleus_button = QPushButton("Add nucleus")
        self.add_nucleus_button.clicked.connect(
            lambda: self.viewer.set_mode(ImageViewer.MODE_ADD_NUCLEUS)
        )
        controls.addWidget(self.add_nucleus_button)

        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self.remove_selected_rows)
        controls.addWidget(remove_btn)

        self.roi_mode_label = QLabel("ROI-only: off")
        controls.addWidget(self.roi_mode_label)
        controls.addStretch(1)
        right.addLayout(controls)

        slider_panel = QVBoxLayout()
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.red_sensitivity_combo = QComboBox(self)
        self.red_sensitivity_combo.addItems([*RED_SENSITIVITY_PRESETS.keys(), "Custom"])
        self.red_sensitivity_combo.setCurrentText(self.project.detection_settings.preset)
        self.red_sensitivity_combo.currentTextChanged.connect(self._detection_preset_changed)
        preset_row.addWidget(self.red_sensitivity_combo)
        preset_row.addStretch(1)
        slider_panel.addLayout(preset_row)
        self.red_sensitivity_slider, self.red_sensitivity_spin = self._make_detection_slider(
            "Red sensitivity", self.project.detection_settings.red_sensitivity, slider_panel
        )
        self.black_sensitivity_slider, self.black_sensitivity_spin = self._make_detection_slider(
            "Black sensitivity", self.project.detection_settings.black_sensitivity, slider_panel
        )
        self.haze_rejection_slider, self.haze_rejection_spin = self._make_detection_slider(
            "Haze rejection", self.project.detection_settings.haze_rejection, slider_panel
        )
        self.cluster_sensitivity_slider, self.cluster_sensitivity_spin = self._make_detection_slider(
            "Cluster sensitivity", self.project.detection_settings.cluster_sensitivity, slider_panel
        )
        right.addLayout(slider_panel)

        dot_controls = QHBoxLayout()
        self.detect_dots_button = QPushButton("Detect dots")
        self.detect_dots_button.clicked.connect(self.detect_dots_for_selected_nucleus)
        dot_controls.addWidget(self.detect_dots_button)

        self.redetect_dots_button = QPushButton("Re-detect current nucleus")
        self.redetect_dots_button.clicked.connect(self.detect_dots_for_selected_nucleus)
        dot_controls.addWidget(self.redetect_dots_button)

        self.apply_detected_counts_button = QPushButton("Apply detected counts")
        self.apply_detected_counts_button.clicked.connect(self.apply_detected_counts_to_selected_nucleus)
        dot_controls.addWidget(self.apply_detected_counts_button)

        self.clear_dot_candidates_button = QPushButton("Clear dot candidates")
        self.clear_dot_candidates_button.clicked.connect(self.clear_dot_candidates_for_selected_nucleus)
        dot_controls.addWidget(self.clear_dot_candidates_button)
        right.addLayout(dot_controls)

        self.dot_candidates_label = QLabel("Dot candidates: select a nucleus, then Detect dots")
        self.dot_candidates_label.setWordWrap(True)
        right.addWidget(self.dot_candidates_label)

        self.selected_nucleus_label = QLabel()
        self.selected_nucleus_label.setWordWrap(True)
        self.selected_nucleus_label.setStyleSheet(
            "background: #fff8c5; border: 1px solid #d6b300; padding: 6px;"
        )
        right.addWidget(self.selected_nucleus_label)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        right.addWidget(self.summary_label)

        disclaimer = QLabel(RESEARCH_USE_DISCLAIMER)
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("color: #666;")
        right.addWidget(disclaimer)


    def _build_shortcuts(self) -> None:
        """Register nucleus-edit shortcuts on the main window and children."""
        self._nucleus_shortcuts: list[QShortcut] = []
        for key_sequence, handler in [
            ("B", lambda: self._increment_selected_nucleus_count("her2_black", 1)),
            ("Shift+B", lambda: self._increment_selected_nucleus_count("her2_black", -1)),
            ("R", lambda: self._increment_selected_nucleus_count("cep17_red", 1)),
            ("Shift+R", lambda: self._increment_selected_nucleus_count("cep17_red", -1)),
            ("S", lambda: self._increment_selected_nucleus_count("small_cluster_count", 1)),
            ("Shift+S", lambda: self._increment_selected_nucleus_count("small_cluster_count", -1)),
            ("L", lambda: self._increment_selected_nucleus_count("large_cluster_count", 1)),
            ("Shift+L", lambda: self._increment_selected_nucleus_count("large_cluster_count", -1)),
            ("I", self._toggle_selected_nucleus_included),
            ("Delete", self.remove_selected_nucleus),
        ]:
            shortcut = QShortcut(QKeySequence(key_sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
            self._nucleus_shortcuts.append(shortcut)

    def _shortcut_should_be_ignored(self, *, ignore_spin_box_focus: bool = False) -> bool:
        """Avoid changing counts while the user is directly editing cell text/numbers."""
        focus_widget = QApplication.focusWidget()
        if focus_widget is None:
            return False
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QPlainTextEdit)):
            return True
        return ignore_spin_box_focus and isinstance(focus_widget, QAbstractSpinBox)

    def _apply_count_table_column_widths(self) -> None:
        """Apply compact initial widths for the nucleus count table UI."""
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for column, width in TABLE_COLUMN_WIDTHS.items():
            self.table.setColumnWidth(column, width)

    def _make_spin(self, minimum: int = 0, maximum: int = 999, value: int = 0, on_change: Callable | None = None) -> QSpinBox:
        spin = QSpinBox(self)
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        if on_change is not None:
            spin.valueChanged.connect(on_change)
        return spin

    def _make_detection_slider(self, label: str, value: int, parent_layout: QVBoxLayout) -> tuple[QSlider, QSpinBox]:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        slider = QSlider(Qt.Orientation.Horizontal, self)
        slider.setRange(0, 100)
        slider.setValue(value)
        spin = QSpinBox(self)
        spin.setRange(0, 100)
        spin.setValue(value)
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        slider.valueChanged.connect(self._detection_slider_changed)
        row.addWidget(slider, stretch=1)
        row.addWidget(spin)
        parent_layout.addLayout(row)
        return slider, spin

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
        self.last_red_detection_stats = None
        self.last_red_detection_nucleus_id = None
        self.viewer.set_roi(self.project.roi)
        self.viewer.draw_nuclei(self.project.nuclei, self.selected_nucleus_id)

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
        self.selected_nucleus_id = None
        self.last_red_detection_stats = None
        self.last_red_detection_nucleus_id = None
        self._apply_detection_settings_to_ui()
        self.refresh_table_from_project()
        self.viewer.set_roi(self.project.roi)
        self.viewer.draw_nuclei(self.project.nuclei, self.selected_nucleus_id)
        self.update_selected_nucleus_panel()
        self.update_score()

    def _selected_image_path(self) -> str:
        return self.project.image_path or self.viewer.image_path

    def detect_dots_for_selected_nucleus(self) -> None:
        nucleus, row = self._selected_nucleus_and_row()
        if nucleus is None or row is None:
            self.statusBar().showMessage("Select one nucleus before detecting dots")
            return
        image_path = self._selected_image_path()
        if not image_path or not Path(image_path).exists():
            QMessageBox.warning(self, "Detect dots", "Open an image before detecting dots.")
            return
        image = Image.open(image_path).convert("RGB")
        params = self._current_detection_params()
        self.last_detection_params = params
        nucleus.black_dot_candidates = detect_black_dots(
            image, nucleus.x, nucleus.y, nucleus.radius_x, nucleus.radius_y, params
        )
        nucleus.black_cluster_candidates = detect_black_cluster_candidates(
            image, nucleus.x, nucleus.y, nucleus.radius_x, nucleus.radius_y, params
        )
        red_result = detect_red_dots_with_debug(
            image, nucleus.x, nucleus.y, nucleus.radius_x, nucleus.radius_y, params
        )
        nucleus.red_dot_candidates = red_result.candidates
        # Backward-compatible storage exists for older JSON files, but new detection
        # no longer creates display-only overlap review candidates.
        nucleus.overlap_dot_candidates = []
        self.last_red_detection_stats = red_result.stats
        self.last_red_detection_nucleus_id = nucleus.nucleus_id
        self.viewer.draw_nuclei(self.project.nuclei, self.selected_nucleus_id)
        self.update_selected_nucleus_panel()
        self.statusBar().showMessage(
            f"Detected candidates for nucleus #{nucleus.nucleus_id}: "
            f"HER2 black={len(nucleus.black_dot_candidates)}, CEP17 red={len(nucleus.red_dot_candidates)}, "
            f"cluster review={len(nucleus.black_cluster_candidates)}"
        )

    def apply_detected_counts_to_selected_nucleus(self) -> None:
        nucleus, row = self._selected_nucleus_and_row()
        if nucleus is None or row is None:
            self.statusBar().showMessage("Select one nucleus before applying detected counts")
            return
        nucleus.her2_black = len(nucleus.black_dot_candidates)
        nucleus.cep17_red = len(nucleus.red_dot_candidates)
        large_red_count = self._large_red_candidate_count(nucleus)
        self._refresh_after_selected_nucleus_edit(row)
        review_notes = []
        if large_red_count:
            review_notes.append("large red candidate included as 1; please review manually")
        if nucleus.black_cluster_candidates:
            review_notes.append("black cluster review candidates not applied")
        review_note = f"; {'; '.join(review_notes)}" if review_notes else ""
        self.statusBar().showMessage(
            f"Applied detected counts to nucleus #{nucleus.nucleus_id}; manual edits remain enabled"
            f"{review_note}"
        )

    def clear_dot_candidates_for_selected_nucleus(self) -> None:
        nucleus, row = self._selected_nucleus_and_row()
        if nucleus is None or row is None:
            self.statusBar().showMessage("Select one nucleus before clearing dot candidates")
            return
        nucleus.black_dot_candidates.clear()
        nucleus.red_dot_candidates.clear()
        nucleus.overlap_dot_candidates.clear()
        nucleus.black_cluster_candidates.clear()
        self.last_red_detection_stats = None
        self.last_red_detection_nucleus_id = None
        self.viewer.draw_nuclei(self.project.nuclei, self.selected_nucleus_id)
        self.update_selected_nucleus_panel()
        self.statusBar().showMessage(f"Cleared dot candidates for nucleus #{nucleus.nucleus_id}")

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
        self.viewer.set_mode(ImageViewer.MODE_SELECT_EDIT)
        self.select_nucleus_by_id(nucleus.nucleus_id)
        self.update_score()


    def update_nucleus_roi(self, nucleus_id: int, x: float, y: float, radius_x: float, radius_y: float) -> None:
        row = self._row_for_nucleus_id(nucleus_id)
        if row is None:
            return
        nucleus = self.project.nuclei[row]
        nucleus.x = float(x)
        nucleus.y = float(y)
        nucleus.radius_x = float(radius_x)
        nucleus.radius_y = float(radius_y)
        nucleus.black_dot_candidates.clear()
        nucleus.red_dot_candidates.clear()
        nucleus.overlap_dot_candidates.clear()
        nucleus.black_cluster_candidates.clear()
        self.last_red_detection_stats = None
        self.last_red_detection_nucleus_id = None
        self._refresh_after_selected_nucleus_edit(row)
        self.statusBar().showMessage(
            "ROI changed; dot candidates cleared. Please run Detect dots again."
        )

    def select_nucleus_by_id(self, nucleus_id: int | None) -> None:
        if nucleus_id is not None and not any(n.nucleus_id == nucleus_id for n in self.project.nuclei):
            nucleus_id = None
        if self.selected_nucleus_id == nucleus_id:
            self._sync_table_selection_to_selected_nucleus()
            self.update_selected_nucleus_panel()
            return
        self.selected_nucleus_id = nucleus_id
        self._sync_table_selection_to_selected_nucleus()
        self.viewer.draw_nuclei(self.project.nuclei, self.selected_nucleus_id)
        self.update_selected_nucleus_panel()

    def _sync_table_selection_to_selected_nucleus(self) -> None:
        self._updating_table = True
        self.table.clearSelection()
        if self.selected_nucleus_id is not None:
            row = self._row_for_nucleus_id(self.selected_nucleus_id)
            if row is not None:
                self.table.selectRow(row)
                self.table.setCurrentCell(row, COL_ID)
        self._updating_table = False

    def _row_for_nucleus_id(self, nucleus_id: int) -> int | None:
        for row, nucleus in enumerate(self.project.nuclei):
            if nucleus.nucleus_id == nucleus_id:
                return row
        return None

    def _table_selection_changed(self) -> None:
        if self._updating_table:
            return
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if rows and rows[0] < len(self.project.nuclei):
            self.select_nucleus_by_id(self.project.nuclei[rows[0]].nucleus_id)
        else:
            self.select_nucleus_by_id(None)


    def _selected_nucleus_and_row(self) -> tuple[NucleusCount, int] | tuple[None, None]:
        if self.selected_nucleus_id is not None:
            row = self._row_for_nucleus_id(self.selected_nucleus_id)
            if row is not None:
                return self.project.nuclei[row], row
        row = self.table.currentRow()
        if 0 <= row < len(self.project.nuclei):
            nucleus = self.project.nuclei[row]
            self.selected_nucleus_id = nucleus.nucleus_id
            return nucleus, row
        return None, None

    def _increment_selected_nucleus_count(self, field_name: str, delta: int) -> None:
        if self._shortcut_should_be_ignored():
            return
        nucleus, row = self._selected_nucleus_and_row()
        if nucleus is None or row is None:
            return
        current_value = int(getattr(nucleus, field_name))
        setattr(nucleus, field_name, max(0, current_value + delta))
        self._refresh_after_selected_nucleus_edit(row)

    def _toggle_selected_nucleus_included(self) -> None:
        if self._shortcut_should_be_ignored():
            return
        nucleus, row = self._selected_nucleus_and_row()
        if nucleus is None or row is None:
            return
        nucleus.included = not nucleus.included
        self._refresh_after_selected_nucleus_edit(row)

    def remove_selected_nucleus(self) -> None:
        if self._shortcut_should_be_ignored(ignore_spin_box_focus=True):
            return
        nucleus, row = self._selected_nucleus_and_row()
        if nucleus is None or row is None:
            return
        del self.project.nuclei[row]
        for index, remaining_nucleus in enumerate(self.project.nuclei, start=1):
            remaining_nucleus.nucleus_id = index
        self.selected_nucleus_id = None
        self.last_red_detection_stats = None
        self.last_red_detection_nucleus_id = None
        self._apply_detection_settings_to_ui()
        self.refresh_table_from_project()
        self.viewer.draw_nuclei(self.project.nuclei, self.selected_nucleus_id)
        self.update_selected_nucleus_panel()
        self.update_score()

    def _refresh_after_selected_nucleus_edit(self, row: int) -> None:
        self._refresh_table_row_from_nucleus(row)
        self._sync_table_selection_to_selected_nucleus()
        self.viewer.draw_nuclei(self.project.nuclei, self.selected_nucleus_id)
        self.update_selected_nucleus_panel()
        self.update_score()

    def _refresh_table_row_from_nucleus(self, row: int) -> None:
        if not 0 <= row < len(self.project.nuclei):
            return
        nucleus = self.project.nuclei[row]
        self._updating_table = True
        for column, value in [
            (COL_ID, str(nucleus.nucleus_id)),
            (COL_X, f"{nucleus.x:.1f}"),
            (COL_Y, f"{nucleus.y:.1f}"),
            (COL_RADIUS_X, f"{nucleus.radius_x:.1f}"),
            (COL_RADIUS_Y, f"{nucleus.radius_y:.1f}"),
            (COL_EFFECTIVE_HER2, str(nucleus.effective_her2)),
        ]:
            item = self.table.item(row, column)
            if item is not None:
                item.setText(value)
        for column, value in [
            (COL_HER2, nucleus.her2_black),
            (COL_SMALL_CLUSTER, nucleus.small_cluster_count),
            (COL_LARGE_CLUSTER, nucleus.large_cluster_count),
            (COL_MANUAL_ADD, nucleus.manual_cluster_add),
            (COL_CEP17, nucleus.cep17_red),
        ]:
            widget = self.table.cellWidget(row, column)
            if isinstance(widget, QSpinBox):
                blocker = QSignalBlocker(widget)
                widget.setValue(int(value))
                del blocker
        included_widget = self.table.cellWidget(row, COL_INCLUDED)
        if isinstance(included_widget, QCheckBox):
            blocker = QSignalBlocker(included_widget)
            included_widget.setChecked(nucleus.included)
            del blocker
        self._updating_table = False

    def update_selected_nucleus_panel(self) -> None:
        nucleus = next((n for n in self.project.nuclei if n.nucleus_id == self.selected_nucleus_id), None)
        if nucleus is None:
            self.selected_nucleus_label.setText("Selected nucleus: none")
            self.dot_candidates_label.setText("Dot candidates: select a nucleus, then Detect dots")
            return
        status = "included" if nucleus.included else "excluded"
        red_debug_lines = self._red_debug_lines(nucleus)
        self.selected_nucleus_label.setText(
            "\n".join(
                [
                    f"Selected nucleus: #{nucleus.nucleus_id} ({status})",
                    f"Center: X={nucleus.x:.1f}, Y={nucleus.y:.1f}",
                    f"ROI radii: Rx={nucleus.radius_x:.1f}, Ry={nucleus.radius_y:.1f}",
                    f"HER2: {nucleus.her2_black}",
                    f"CEP17: {nucleus.cep17_red}",
                    f"Small cluster: {nucleus.small_cluster_count}",
                    f"Large cluster: {nucleus.large_cluster_count}",
                    f"Manual HER2 add: {nucleus.manual_cluster_add}",
                    f"Effective HER2: {nucleus.effective_her2}",
                    f"Detected HER2 candidates: {len(nucleus.black_dot_candidates)}",
                    f"Detected CEP17 candidates: {len(nucleus.red_dot_candidates)}",
                    f"Black cluster review candidates: {len(nucleus.black_cluster_candidates)}",
                    f"Large red candidates: {self._large_red_candidate_count(nucleus)}",
                    f"Red haze rejected components: {self._red_haze_rejected_count(nucleus)}",
                    *red_debug_lines,
                ]
            )
        )
        self.dot_candidates_label.setText(
            f"Dot candidates for selected nucleus: "
            f"HER2 black={len(nucleus.black_dot_candidates)}, CEP17 red={len(nucleus.red_dot_candidates)}, "
            f"cluster review={len(nucleus.black_cluster_candidates)} "
            f"(large red={self._large_red_candidate_count(nucleus)}). "
            "Red signals inside or near black clusters are included as CEP17 candidates when red/magenta signal is detected. "
            "Black cluster candidates are not automatically applied; please review and enter S/L-cluster manually if appropriate."
        )

    def _red_debug_lines(self, nucleus: NucleusCount) -> list[str]:
        params = self.last_detection_params or self._current_detection_params()
        lines = [
            "Detection sliders:",
            f"Red sensitivity: {params.red_sensitivity}",
            f"Black sensitivity: {params.black_sensitivity}",
            f"Haze rejection: {params.haze_rejection}",
            f"Cluster sensitivity: {params.cluster_sensitivity}",
            f"red_min_area: {params.red_min_area:.1f}",
            f"red_max_area: {params.red_max_area:.1f}",
            f"black_min_area: {params.black_min_area:.1f}",
            f"black_max_area: {params.black_max_area:.1f}",
        ]
        if self.last_red_detection_stats is None or self.last_red_detection_nucleus_id != nucleus.nucleus_id:
            return lines
        stats = self.last_red_detection_stats
        return [
            *lines,
            f"Red mask pixels: {stats.mask_pixels}",
            f"Red connected components: {stats.connected_components}",
            f"Red components after area filter: {stats.area_pass_components}",
            f"Red components after circularity filter: {stats.circularity_pass_components}",
            f"Final CEP17 candidates: {stats.final_cep17_candidates}",
            f"Large red candidates: {stats.large_red_candidates}",
            f"Red haze rejected components: {stats.red_haze_rejected_components}",
            f"Merged duplicate red candidates: {stats.merged_duplicate_red_candidates}",
            "Note: Final CEP17 candidates are applied; black cluster review candidates are display-only.",
        ]

    def _large_red_candidate_count(self, nucleus: NucleusCount) -> int:
        return sum(1 for candidate in nucleus.red_dot_candidates if candidate.color_type == "large_red")

    def _red_haze_rejected_count(self, nucleus: NucleusCount) -> int:
        if self.last_red_detection_stats is None or self.last_red_detection_nucleus_id != nucleus.nucleus_id:
            return 0
        return self.last_red_detection_stats.red_haze_rejected_components

    def _current_detection_params(self) -> DotDetectionParams:
        self.project.detection_settings = DetectionSettings(
            preset=self.red_sensitivity_combo.currentText(),
            red_sensitivity=self.red_sensitivity_slider.value(),
            black_sensitivity=self.black_sensitivity_slider.value(),
            haze_rejection=self.haze_rejection_slider.value(),
            cluster_sensitivity=self.cluster_sensitivity_slider.value(),
        )
        return params_from_sliders(
            self.project.detection_settings.red_sensitivity,
            self.project.detection_settings.black_sensitivity,
            self.project.detection_settings.haze_rejection,
            self.project.detection_settings.cluster_sensitivity,
        )

    def _apply_detection_settings_to_ui(self) -> None:
        settings = self.project.detection_settings
        for slider, spin, value in [
            (self.red_sensitivity_slider, self.red_sensitivity_spin, settings.red_sensitivity),
            (self.black_sensitivity_slider, self.black_sensitivity_spin, settings.black_sensitivity),
            (self.haze_rejection_slider, self.haze_rejection_spin, settings.haze_rejection),
            (self.cluster_sensitivity_slider, self.cluster_sensitivity_spin, settings.cluster_sensitivity),
        ]:
            slider_blocker = QSignalBlocker(slider)
            spin_blocker = QSignalBlocker(spin)
            slider.setValue(value)
            spin.setValue(value)
            del spin_blocker
            del slider_blocker
        self.red_sensitivity_combo.setCurrentText(settings.preset if settings.preset in {"Conservative", "Standard", "Sensitive", "Custom"} else "Custom")

    def _detection_preset_changed(self, preset_name: str) -> None:
        preset_values = {
            "Conservative": (25, 40, 70, 35),
            "Standard": (50, 50, 50, 50),
            "Sensitive": (80, 70, 30, 80),
        }
        if preset_name in preset_values:
            self._applying_detection_preset = True
            for slider, spin, value in zip(
                [self.red_sensitivity_slider, self.black_sensitivity_slider, self.haze_rejection_slider, self.cluster_sensitivity_slider],
                [self.red_sensitivity_spin, self.black_sensitivity_spin, self.haze_rejection_spin, self.cluster_sensitivity_spin],
                preset_values[preset_name],
            ):
                slider.setValue(value)
                spin.setValue(value)
            self._applying_detection_preset = False
        self.last_red_detection_stats = None
        self.last_red_detection_nucleus_id = None
        self._current_detection_params()
        self.update_selected_nucleus_panel()

    def _detection_slider_changed(self) -> None:
        if self._applying_detection_preset:
            return
        if self.red_sensitivity_combo.currentText() != "Custom":
            blocker = QSignalBlocker(self.red_sensitivity_combo)
            self.red_sensitivity_combo.setCurrentText("Custom")
            del blocker
        self.last_red_detection_stats = None
        self.last_red_detection_nucleus_id = None
        self._current_detection_params()
        self.update_selected_nucleus_panel()

    def _append_row(self, nucleus: NucleusCount) -> None:
        self._updating_table = True
        row = self.table.rowCount()
        self.table.insertRow(row)

        for col, value, editable in [
            (COL_ID, str(nucleus.nucleus_id), False),
            (COL_X, f"{nucleus.x:.1f}", False),
            (COL_Y, f"{nucleus.y:.1f}", False),
            (COL_RADIUS_X, f"{nucleus.radius_x:.1f}", False),
            (COL_RADIUS_Y, f"{nucleus.radius_y:.1f}", False),
            (COL_EFFECTIVE_HER2, str(nucleus.effective_her2), False),
            (COL_COMMENT, nucleus.comment, True),
        ]:
            item = QTableWidgetItem(value)
            if not editable:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, col, item)

        her2 = self._make_spin(value=nucleus.her2_black, on_change=self._sync_project_from_table)
        small_cluster = self._make_spin(value=nucleus.small_cluster_count, on_change=self._sync_project_from_table)
        large_cluster = self._make_spin(value=nucleus.large_cluster_count, on_change=self._sync_project_from_table)
        manual_add = self._make_spin(value=nucleus.manual_cluster_add, on_change=self._sync_project_from_table)
        cep17 = self._make_spin(value=nucleus.cep17_red, on_change=self._sync_project_from_table)
        included = QCheckBox()
        included.setChecked(nucleus.included)
        included.stateChanged.connect(self._sync_project_from_table)

        self.table.setCellWidget(row, COL_HER2, her2)
        self.table.setCellWidget(row, COL_SMALL_CLUSTER, small_cluster)
        self.table.setCellWidget(row, COL_LARGE_CLUSTER, large_cluster)
        self.table.setCellWidget(row, COL_MANUAL_ADD, manual_add)
        self.table.setCellWidget(row, COL_CEP17, cep17)
        self.table.setCellWidget(row, COL_INCLUDED, included)
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
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self.project.nuclei):
                del self.project.nuclei[row]
        for index, nucleus in enumerate(self.project.nuclei, start=1):
            nucleus.nucleus_id = index
        self.selected_nucleus_id = None
        self.last_red_detection_stats = None
        self.last_red_detection_nucleus_id = None
        self._apply_detection_settings_to_ui()
        self.refresh_table_from_project()
        self.viewer.draw_nuclei(self.project.nuclei, self.selected_nucleus_id)
        self.update_selected_nucleus_panel()
        self.update_score()

    def _table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_table:
            return
        if item.column() == COL_COMMENT and item.row() < len(self.project.nuclei):
            self.project.nuclei[item.row()].comment = item.text()
            self.update_score()

    def _sync_project_from_table(self) -> None:
        if self._updating_table:
            return
        for row, nucleus in enumerate(self.project.nuclei):
            her2 = self.table.cellWidget(row, COL_HER2)
            small_cluster = self.table.cellWidget(row, COL_SMALL_CLUSTER)
            large_cluster = self.table.cellWidget(row, COL_LARGE_CLUSTER)
            manual_add = self.table.cellWidget(row, COL_MANUAL_ADD)
            cep17 = self.table.cellWidget(row, COL_CEP17)
            included = self.table.cellWidget(row, COL_INCLUDED)
            if isinstance(her2, QSpinBox):
                nucleus.her2_black = her2.value()
            if isinstance(small_cluster, QSpinBox):
                nucleus.small_cluster_count = small_cluster.value()
            if isinstance(large_cluster, QSpinBox):
                nucleus.large_cluster_count = large_cluster.value()
            if isinstance(manual_add, QSpinBox):
                nucleus.manual_cluster_add = manual_add.value()
            if isinstance(cep17, QSpinBox):
                nucleus.cep17_red = cep17.value()
            if isinstance(included, QCheckBox):
                nucleus.included = included.isChecked()
            effective_item = self.table.item(row, COL_EFFECTIVE_HER2)
            if effective_item is not None:
                effective_item.setText(str(nucleus.effective_her2))
        self.viewer.draw_nuclei(self.project.nuclei, self.selected_nucleus_id)
        self.update_selected_nucleus_panel()
        self.update_score()

    def update_score(self) -> None:
        result = calculate_score(self.project.nuclei)
        ratio = f"{result.her2_cep17_ratio:.3f}" if result.her2_cep17_ratio is not None else "N/A"
        avg = f"{result.average_her2_copy_number:.3f}" if result.average_her2_copy_number is not None else "N/A"
        warnings = "\n".join(f"• {w}" for w in result.warnings) if result.warnings else "None"
        count_workflow = self._count_workflow_status(result.included_cell_count)

        self.summary_label.setText(
            "\n".join(
                [
                    f"Included nuclei: {result.included_cell_count}",
                    f"20/40 count workflow: {count_workflow}",
                    f"Total HER2 (effective): {result.total_her2}",
                    f"Total CEP17: {result.total_cep17}",
                    f"HER2/CEP17 ratio: {ratio}",
                    f"Average HER2 copy number: {avg}",
                    f"ISH group: {result.ish_group}",
                    f"Warnings: {warnings}",
                ]
            )
        )

    def _count_workflow_status(self, included_cell_count: int) -> str:
        if included_cell_count < 20:
            return f"{included_cell_count}/20 nuclei counted"
        if included_cell_count < 40:
            return f"20-nucleus checkpoint reached ({included_cell_count}/40 if additional counting is needed)"
        return f"40-nucleus count complete ({included_cell_count}/40)"
