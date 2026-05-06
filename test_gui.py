from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, Qt
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
    viewport_pos = window.viewer.mapFromScene(target)
    QTest.mouseClick(window.viewer.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, viewport_pos)
    qt_app.processEvents()

    assert len(window.project.nuclei) == 1
    assert window.project.nuclei[0].x == pytest.approx(target.x(), abs=0.51)
    assert window.project.nuclei[0].y == pytest.approx(target.y(), abs=0.51)
    assert window.table.item(0, 1).text() == "123.0"
    assert window.table.item(0, 2).text() == "87.0"


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
    viewport_pos = viewer.mapFromScene(target)
    QTest.mouseClick(viewer.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, viewport_pos)
    qt_app.processEvents()

    assert clicked == pytest.approx([(target.x(), target.y())], abs=0.51)
