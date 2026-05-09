from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView

from her2dish.core.models import NucleusCount, RoiRectangle


class ImageViewer(QGraphicsView):
    """Zoomable/pannable image viewer that emits image-coordinate clicks and ROIs."""

    nucleusClicked = Signal(float, float)
    nucleusSelected = Signal(int)
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
        self._drawn_nuclei: list[NucleusCount] = []
        self._selected_nucleus_id: int | None = None
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
        self._drawn_nuclei.clear()
        self._selected_nucleus_id = None
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

    def draw_nuclei(self, nuclei: list[NucleusCount], selected_nucleus_id: int | None = None) -> None:
        self._drawn_nuclei = list(nuclei)
        self._selected_nucleus_id = selected_nucleus_id
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()
        for nucleus in nuclei:
            is_selected = nucleus.nucleus_id == selected_nucleus_id
            color = QColor("yellow") if is_selected else QColor("lime") if nucleus.included else QColor("gray")
            pen = QPen(color, 5 if is_selected else 3)
            if not nucleus.included and not is_selected:
                pen.setStyle(Qt.PenStyle.DashLine)
            ellipse = QGraphicsEllipseItem(
                nucleus.x - nucleus.radius_x,
                nucleus.y - nucleus.radius_y,
                nucleus.radius_x * 2,
                nucleus.radius_y * 2,
            )
            ellipse.setPen(pen)
            ellipse.setData(0, nucleus.nucleus_id)
            ellipse.setToolTip(f"Nucleus #{nucleus.nucleus_id}")
            ellipse.setZValue(12 if is_selected else 10)
            self._scene.addItem(ellipse)
            text = QGraphicsSimpleTextItem(f"#{nucleus.nucleus_id} H{nucleus.effective_her2}/C{nucleus.cep17_red}")
            text.setBrush(color)
            text.setData(0, nucleus.nucleus_id)
            text.setToolTip(f"Nucleus #{nucleus.nucleus_id}")
            text.setPos(nucleus.x + nucleus.radius_x + 3, nucleus.y - nucleus.radius_y)
            text.setZValue(13 if is_selected else 11)
            self._scene.addItem(text)
            self._overlay_items.extend([ellipse, text])
        self._draw_selected_dot_candidates()

    def _draw_selected_dot_candidates(self) -> None:
        if self._selected_nucleus_id is None:
            return
        nucleus = next((n for n in self._drawn_nuclei if n.nucleus_id == self._selected_nucleus_id), None)
        if nucleus is None:
            return
        for candidate, color_name in [
            *((candidate, "deepskyblue") for candidate in nucleus.black_dot_candidates),
            *((candidate, "magenta") for candidate in nucleus.red_dot_candidates),
        ]:
            radius = max(3.0, min(8.0, (float(candidate.area) ** 0.5) / 2.0 + 2.0))
            dot = QGraphicsEllipseItem(candidate.x - radius, candidate.y - radius, radius * 2.0, radius * 2.0)
            pen = QPen(QColor(color_name), 2)
            dot.setPen(pen)
            dot.setBrush(Qt.BrushStyle.NoBrush)
            dot.setData(1, candidate.color_type)
            dot.setToolTip(f"{candidate.color_type} dot candidate: area={candidate.area:.1f}")
            dot.setZValue(20)
            self._scene.addItem(dot)
            self._overlay_items.append(dot)

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
        image_pos = self.image_position_from_viewport_position(event.position())
        if event.button() == Qt.MouseButton.LeftButton and self._mode == self.MODE_ADD_NUCLEUS:
            if image_pos is not None:
                self.nucleusClicked.emit(image_pos.x(), image_pos.y())
            return
        if event.button() == Qt.MouseButton.LeftButton and self._mode == self.MODE_RECT_ROI:
            if image_pos is None:
                return
            self._roi_start = image_pos
            self._drawing_roi = True
            self.set_roi(RoiRectangle(image_pos.x(), image_pos.y(), 0, 0))
            return
        if event.button() == Qt.MouseButton.LeftButton:
            nucleus_id = self._nucleus_id_at_viewport_position(event.position(), image_pos)
            if nucleus_id is not None:
                self.nucleusSelected.emit(nucleus_id)
                return
        super().mousePressEvent(event)

    def _nucleus_id_at_viewport_position(self, viewport_pos: QPoint | QPointF, image_pos: QPointF | None) -> int | None:
        scene_pos = self.scene_position_from_viewport_position(viewport_pos)
        if scene_pos is not None:
            for item in self._scene.items(scene_pos):
                nucleus_id = item.data(0)
                if isinstance(nucleus_id, int):
                    return nucleus_id
        if image_pos is None:
            return None
        for nucleus in reversed(self._drawn_nuclei):
            radius_x = nucleus.radius_x or 1.0
            radius_y = nucleus.radius_y or 1.0
            dx = (image_pos.x() - nucleus.x) / radius_x
            dy = (image_pos.y() - nucleus.y) / radius_y
            if dx * dx + dy * dy <= 1.0:
                return nucleus.nucleus_id
        return None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt override
        image_pos = self.image_position_from_viewport_position(event.position())
        if image_pos is None:
            self.statusChanged.emit("outside image")
        else:
            self.statusChanged.emit(f"x={image_pos.x():.1f}, y={image_pos.y():.1f}")
        if self._drawing_roi and self._roi_start is not None:
            if image_pos is None:
                return
            roi = RoiRectangle(
                self._roi_start.x(),
                self._roi_start.y(),
                image_pos.x() - self._roi_start.x(),
                image_pos.y() - self._roi_start.y(),
            ).normalized()
            self.set_roi(roi)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton and self._drawing_roi and self._roi_start is not None:
            image_pos = self.image_position_from_viewport_position(event.position())
            if image_pos is None:
                self._drawing_roi = False
                self._roi_start = None
                return
            roi = RoiRectangle(
                self._roi_start.x(),
                self._roi_start.y(),
                image_pos.x() - self._roi_start.x(),
                image_pos.y() - self._roi_start.y(),
            ).normalized()
            self._drawing_roi = False
            self._roi_start = None
            self.set_roi(roi)
            self.roiChanged.emit(roi)
            return
        super().mouseReleaseEvent(event)

    def image_position_from_viewport_position(self, viewport_pos: QPoint | QPointF) -> QPointF | None:
        """Convert a viewport mouse position to original image coordinates.

        The scene may be zoomed or panned, but nuclei must be stored in
        original image pixels. Mapping through the pixmap item keeps the
        saved coordinates independent from the current view transform.  Qt
        mouse events can carry sub-pixel ``QPointF`` positions, so use the
        inverse viewport transform directly instead of rounding through
        ``mapToScene(QPoint)``.
        """
        if self._pixmap_item is None:
            return None
        scene_pos = self.scene_position_from_viewport_position(viewport_pos)
        if scene_pos is None:
            return None
        image_pos = self._pixmap_item.mapFromScene(scene_pos)
        if not self._point_is_on_image(image_pos):
            return None
        return QPointF(image_pos)

    def scene_position_from_viewport_position(self, viewport_pos: QPoint | QPointF) -> QPointF | None:
        """Map a viewport position to scene coordinates without integer rounding."""
        viewport_point = QPointF(viewport_pos)
        inverse_transform, invertible = self.viewportTransform().inverted()
        if not invertible:
            return None
        return QPointF(inverse_transform.map(viewport_point))

    def viewport_position_from_image_position(self, image_pos: QPoint | QPointF) -> QPointF | None:
        """Map original image coordinates to a floating-point viewport position."""
        if self._pixmap_item is None:
            return None
        scene_pos = self._pixmap_item.mapToScene(QPointF(image_pos))
        return QPointF(self.viewportTransform().map(scene_pos))

    def _point_is_on_image(self, point: QPointF) -> bool:
        if self._pixmap_item is None:
            return False
        return self._pixmap_item.boundingRect().contains(point)
