from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from image_viewer import ImageViewer
from main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _write_image(path):
    pillow = pytest.importorskip("PIL.Image")
    pillow.new("RGB", (320, 240), "white").save(path)


def _clickable_viewport_point_for_image_position(viewer: ImageViewer, image_pos: QPointF) -> tuple[QPoint, QPointF]:
    """Return the integer viewport pixel QTest can click and its true image coordinate."""
    viewport_pos = viewer.viewport_position_from_image_position(image_pos)
    assert viewport_pos is not None
    click_pos = QPoint(round(viewport_pos.x()), round(viewport_pos.y()))
    clicked_image_pos = viewer.image_position_from_viewport_position(click_pos)
    assert clicked_image_pos is not None
    return click_pos, clicked_image_pos


def test_panel_add_nucleus_button_enters_click_mode_without_zero_row(qt_app, tmp_path):
    image_path = tmp_path / "source.png"
    _write_image(image_path)

    window = MainWindow()
    window.viewer.load_image(image_path)
    window.show()
    qt_app.processEvents()

    QTest.mouseClick(window.add_nucleus_button, Qt.MouseButton.LeftButton)
    qt_app.processEvents()

    assert window.project.nuclei == []
    assert window.table.rowCount() == 0

    target = QPointF(123.0, 87.0)
    viewport_pos, expected = _clickable_viewport_point_for_image_position(window.viewer, target)
    QTest.mouseClick(window.viewer.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, viewport_pos)
    qt_app.processEvents()

    assert len(window.project.nuclei) == 1
    assert window.project.nuclei[0].x == pytest.approx(expected.x(), abs=0.01)
    assert window.project.nuclei[0].y == pytest.approx(expected.y(), abs=0.01)
    assert window.table.item(0, 1).text() == f"{expected.x():.1f}"
    assert window.table.item(0, 2).text() == f"{expected.y():.1f}"


def test_viewer_coordinate_helpers_preserve_fractional_positions(qt_app, tmp_path):
    image_path = tmp_path / "source.png"
    _write_image(image_path)
    viewer = ImageViewer()
    viewer.resize(640, 480)
    viewer.load_image(image_path)
    viewer.scale(1.75, 1.75)
    viewer.centerOn(180.0, 120.0)
    viewer.show()
    qt_app.processEvents()

    target = QPointF(180.25, 120.75)
    viewport_pos = viewer.viewport_position_from_image_position(target)
    assert viewport_pos is not None

    image_pos = viewer.image_position_from_viewport_position(viewport_pos)
    assert image_pos is not None
    assert image_pos.x() == pytest.approx(target.x(), abs=0.001)
    assert image_pos.y() == pytest.approx(target.y(), abs=0.001)


def test_viewer_click_coordinates_survive_zoom_and_pan(qt_app, tmp_path):
    image_path = tmp_path / "source.png"
    _write_image(image_path)
    viewer = ImageViewer()
    viewer.resize(640, 480)
    viewer.load_image(image_path)
    viewer.set_mode(ImageViewer.MODE_ADD_NUCLEUS)
    viewer.scale(1.75, 1.75)
    viewer.centerOn(180.0, 120.0)
    viewer.show()
    qt_app.processEvents()

    clicked = []
    viewer.nucleusClicked.connect(lambda x, y: clicked.append((x, y)))

    target = QPointF(180.0, 120.0)
    viewport_pos, expected = _clickable_viewport_point_for_image_position(viewer, target)
    QTest.mouseClick(viewer.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, viewport_pos)
    qt_app.processEvents()

    assert clicked == pytest.approx([(expected.x(), expected.y())], abs=0.01)


def test_count_table_cluster_columns_update_effective_her2(qt_app):
    window = MainWindow()
    window.add_nucleus_at(10, 20)
    qt_app.processEvents()

    headers = [window.table.horizontalHeaderItem(i).text() for i in range(window.table.columnCount())]
    assert headers[3:9] == [
        "HER2 dots",
        "Small cluster",
        "Large cluster",
        "Manual HER2 add",
        "Effective HER2",
        "CEP17",
    ]

    window.table.cellWidget(0, 3).setValue(2)
    window.table.cellWidget(0, 4).setValue(1)
    window.table.cellWidget(0, 5).setValue(1)
    window.table.cellWidget(0, 6).setValue(3)
    window.table.cellWidget(0, 8).setValue(5)
    qt_app.processEvents()

    nucleus = window.project.nuclei[0]
    assert nucleus.effective_her2 == 23
    assert nucleus.cep17_red == 5
    assert window.table.item(0, 7).text() == "23"
    assert "Total HER2 (effective): 23" in window.summary_label.text()
