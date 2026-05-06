from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView

from her2dish.core.models import NucleusCount, RoiRectangle


class ImageViewer(QGraphicsView):
    """Zoomable/pannable image viewer that emits image-coordinate clicks and ROIs."""

    nucleusClicked = Signal(float, float)
    roiChanged = Signal(object)
    statusChanged = Signal(str)

    MODE_PAN = "pan"
    MODE_ADD_NUCLEUS = "add_nucleus"
    MODE_RECT_ROI = "rect_roi"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._image_path = ""
        self._mode = self.MODE_PAN
        self._roi_item: QGraphicsRectItem | None = None
        self._roi_start: QPointF | None = None
        self._drawing_roi = False
        self._overlay_items: list[object] = []
        self._roi: RoiRectangle | None = None

    @property
    def image_path(self) -> str:
        return self._image_path

    def has_image(self) -> bool:
        return self._pixmap_item is not None

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if mode == self.MODE_PAN else QGraphicsView.DragMode.NoDrag)
        self.statusChanged.emit(f"Mode: {mode.replace('_', ' ')}")

    def load_image(self, path: str | Path) -> None:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            raise ValueError(f"Could not read image: {path}")
        pixmap = QPixmap.fromImage(image)
        self._scene.clear()
        self._overlay_items.clear()
        self._roi_item = None
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._pixmap_item.setZValue(0)
        self._image_path = str(path)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.resetTransform()
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.statusChanged.emit(f"Loaded image: {path}")

    def set_roi(self, roi: RoiRectangle | None) -> None:
        self._roi = roi.normalized() if roi else None
        if self._roi_item is not None:
            self._scene.removeItem(self._roi_item)
            self._roi_item = None
        if self._roi is not None:
            self._roi_item = self._scene.addRect(
                QRectF(self._roi.x, self._roi.y, self._roi.width, self._roi.height),
                QPen(QColor("yellow"), 3),
            )
            self._roi_item.setZValue(5)

    def draw_nuclei(self, nuclei: list[NucleusCount]) -> None:
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()
        for nucleus in nuclei:
            color = QColor("lime") if nucleus.included else QColor("gray")
            pen = QPen(color, 3)
            ellipse = QGraphicsEllipseItem(
                nucleus.x - nucleus.radius_x,
                nucleus.y - nucleus.radius_y,
                nucleus.radius_x * 2,
                nucleus.radius_y * 2,
            )
            ellipse.setPen(pen)
            ellipse.setZValue(10)
            self._scene.addItem(ellipse)
            text = QGraphicsSimpleTextItem(f"#{nucleus.nucleus_id} H{nucleus.effective_her2}/C{nucleus.cep17_red}")
            text.setBrush(color)
            text.setPos(nucleus.x + nucleus.radius_x + 3, nucleus.y - nucleus.radius_y)
            text.setZValue(11)
            self._scene.addItem(text)
            self._overlay_items.extend([ellipse, text])

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not self.has_image():
            super().wheelEvent(event)
            return
        zoom_factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not self.has_image():
            super().mousePressEvent(event)
            return
        scene_pos = self.mapToScene(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and self._mode == self.MODE_ADD_NUCLEUS:
            if self._point_is_on_image(scene_pos):
                self.nucleusClicked.emit(scene_pos.x(), scene_pos.y())
            return
        if event.button() == Qt.MouseButton.LeftButton and self._mode == self.MODE_RECT_ROI:
            self._roi_start = scene_pos
            self._drawing_roi = True
            self.set_roi(RoiRectangle(scene_pos.x(), scene_pos.y(), 0, 0))
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt override
        scene_pos = self.mapToScene(event.position().toPoint())
        self.statusChanged.emit(f"x={scene_pos.x():.1f}, y={scene_pos.y():.1f}")
        if self._drawing_roi and self._roi_start is not None:
            roi = RoiRectangle(
                self._roi_start.x(),
                self._roi_start.y(),
                scene_pos.x() - self._roi_start.x(),
                scene_pos.y() - self._roi_start.y(),
            ).normalized()
            self.set_roi(roi)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton and self._drawing_roi and self._roi_start is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            roi = RoiRectangle(
                self._roi_start.x(),
                self._roi_start.y(),
                scene_pos.x() - self._roi_start.x(),
                scene_pos.y() - self._roi_start.y(),
            ).normalized()
            self._drawing_roi = False
            self._roi_start = None
            self.set_roi(roi)
            self.roiChanged.emit(roi)
            return
        super().mouseReleaseEvent(event)

    def _point_is_on_image(self, point: QPointF) -> bool:
        if self._pixmap_item is None:
            return False
        return self._pixmap_item.boundingRect().contains(point)
