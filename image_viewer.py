from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImageReader, QPainter, QPen, QPixmap, QBrush
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from her2dish.core.constants import MIN_NUCLEUS_RADIUS, NUCLEUS_RESIZE_HANDLE_SIZE
from her2dish.core.models import NucleusCount, RoiRectangle


class ImageViewer(QGraphicsView):
    """Zoomable/pannable image viewer that emits image-coordinate clicks and ROIs."""

    nucleusClicked = Signal(float, float)
    nucleusSelected = Signal(int)
    nucleusRoiChanged = Signal(int, float, float, float, float)
    roiChanged = Signal(object)
    statusChanged = Signal(str)

    MODE_PAN = "pan"
    MODE_SELECT_EDIT = "select_edit"
    MODE_ADD_NUCLEUS = "add_nucleus"
    MODE_RECT_ROI = "rect_roi"

    DRAG_NONE = "none"
    DRAG_MOVE = "move"
    DRAG_RESIZE = "resize"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._image_path = ""
        self._mode = self.MODE_SELECT_EDIT
        self._roi_item: QGraphicsRectItem | None = None
        self._roi_start: QPointF | None = None
        self._drawing_roi = False
        self._overlay_items: list[object] = []
        self._drawn_nuclei: list[NucleusCount] = []
        self._selected_nucleus_id: int | None = None
        self._roi: RoiRectangle | None = None
        self._drag_action = self.DRAG_NONE
        self._drag_nucleus_id: int | None = None
        self._drag_start_image_pos: QPointF | None = None
        self._drag_start_geometry: tuple[float, float, float, float] | None = None

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
            color = QColor("orange") if is_selected else QColor("lime") if nucleus.included else QColor("gray")
            pen = QPen(color, 4 if is_selected else 2)
            if not nucleus.included and not is_selected:
                pen.setStyle(Qt.PenStyle.DashLine)
            ellipse = QGraphicsEllipseItem(
                nucleus.x - nucleus.radius_x,
                nucleus.y - nucleus.radius_y,
                nucleus.radius_x * 2,
                nucleus.radius_y * 2,
            )
            ellipse.setPen(pen)
            ellipse.setBrush(Qt.BrushStyle.NoBrush)
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
            if is_selected:
                self._add_resize_handle(nucleus)
        self._draw_selected_dot_candidates()

    def _add_resize_handle(self, nucleus: NucleusCount) -> None:
        size = NUCLEUS_RESIZE_HANDLE_SIZE
        handle = QGraphicsRectItem(
            nucleus.x + nucleus.radius_x - size / 2,
            nucleus.y + nucleus.radius_y - size / 2,
            size,
            size,
        )
        handle.setPen(QPen(QColor("orange"), 2))
        handle.setBrush(QBrush(QColor("yellow")))
        handle.setData(0, nucleus.nucleus_id)
        handle.setData(1, "resize_handle")
        handle.setToolTip(f"Resize nucleus #{nucleus.nucleus_id}")
        handle.setZValue(30)
        self._scene.addItem(handle)
        self._overlay_items.append(handle)

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
            dot.setPen(QPen(QColor(color_name), 2))
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
        if event.button() == Qt.MouseButton.LeftButton and self._mode == self.MODE_SELECT_EDIT:
            hit = self._nucleus_hit_at_viewport_position(event.position(), image_pos)
            if hit.nucleus_id is not None:
                self.nucleusSelected.emit(hit.nucleus_id)
                if image_pos is not None:
                    self._begin_nucleus_drag(hit.nucleus_id, hit.on_resize_handle, image_pos)
                return
        if event.button() == Qt.MouseButton.LeftButton:
            nucleus_id = self._nucleus_id_at_viewport_position(event.position(), image_pos)
            if nucleus_id is not None:
                self.nucleusSelected.emit(nucleus_id)
                return
        super().mousePressEvent(event)

    def _begin_nucleus_drag(self, nucleus_id: int, resize: bool, image_pos: QPointF) -> None:
        nucleus = next((n for n in self._drawn_nuclei if n.nucleus_id == nucleus_id), None)
        if nucleus is None:
            return
        self._drag_action = self.DRAG_RESIZE if resize else self.DRAG_MOVE
        self._drag_nucleus_id = nucleus_id
        self._drag_start_image_pos = QPointF(image_pos)
        self._drag_start_geometry = (nucleus.x, nucleus.y, nucleus.radius_x, nucleus.radius_y)

    class _Hit:
        def __init__(self, nucleus_id: int | None, on_resize_handle: bool = False) -> None:
            self.nucleus_id = nucleus_id
            self.on_resize_handle = on_resize_handle

    def _nucleus_hit_at_viewport_position(self, viewport_pos: QPoint | QPointF, image_pos: QPointF | None) -> _Hit:
        scene_pos = self.scene_position_from_viewport_position(viewport_pos)
        if scene_pos is not None:
            for item in self._scene.items(scene_pos):
                nucleus_id = item.data(0)
                if isinstance(nucleus_id, int):
                    return self._Hit(nucleus_id, item.data(1) == "resize_handle")
        nucleus_id = self._nucleus_id_at_viewport_position(viewport_pos, image_pos)
        return self._Hit(nucleus_id)

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
        if self._drag_action != self.DRAG_NONE and image_pos is not None:
            self._update_dragged_nucleus(image_pos, keep_aspect=bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
            return
        super().mouseMoveEvent(event)

    def _update_dragged_nucleus(self, image_pos: QPointF, *, keep_aspect: bool) -> None:
        if self._drag_nucleus_id is None or self._drag_start_image_pos is None or self._drag_start_geometry is None:
            return
        nucleus = next((n for n in self._drawn_nuclei if n.nucleus_id == self._drag_nucleus_id), None)
        if nucleus is None:
            return
        start_x, start_y, start_rx, start_ry = self._drag_start_geometry
        dx = image_pos.x() - self._drag_start_image_pos.x()
        dy = image_pos.y() - self._drag_start_image_pos.y()
        if self._drag_action == self.DRAG_MOVE:
            nucleus.x, nucleus.y = self._clamp_center(start_x + dx, start_y + dy, nucleus.radius_x, nucleus.radius_y)
        elif self._drag_action == self.DRAG_RESIZE:
            new_rx = max(MIN_NUCLEUS_RADIUS, start_rx + dx)
            new_ry = max(MIN_NUCLEUS_RADIUS, start_ry + dy)
            if keep_aspect and start_rx > 0 and start_ry > 0:
                scale = max(new_rx / start_rx, new_ry / start_ry)
                new_rx = start_rx * scale
                new_ry = start_ry * scale
            max_rx, max_ry = self._max_radii_for_center(nucleus.x, nucleus.y)
            nucleus.radius_x = min(new_rx, max_rx)
            nucleus.radius_y = min(new_ry, max_ry)
        self.draw_nuclei(self._drawn_nuclei, self._selected_nucleus_id)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton and self._drag_action != self.DRAG_NONE:
            nucleus_id = self._drag_nucleus_id
            start_geometry = self._drag_start_geometry
            nucleus = next((n for n in self._drawn_nuclei if n.nucleus_id == nucleus_id), None)
            self._drag_action = self.DRAG_NONE
            self._drag_nucleus_id = None
            self._drag_start_image_pos = None
            self._drag_start_geometry = None
            if nucleus is not None and start_geometry is not None:
                current_geometry = (nucleus.x, nucleus.y, nucleus.radius_x, nucleus.radius_y)
                if current_geometry != start_geometry:
                    self.nucleusRoiChanged.emit(
                        nucleus.nucleus_id, nucleus.x, nucleus.y, nucleus.radius_x, nucleus.radius_y
                    )
            return
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

    def _clamp_center(self, x: float, y: float, radius_x: float, radius_y: float) -> tuple[float, float]:
        if self._pixmap_item is None:
            return x, y
        rect = self._pixmap_item.boundingRect()
        min_x = rect.left() + radius_x
        max_x = rect.right() - radius_x
        min_y = rect.top() + radius_y
        max_y = rect.bottom() - radius_y
        if min_x > max_x:
            x = rect.center().x()
        else:
            x = min(max(x, min_x), max_x)
        if min_y > max_y:
            y = rect.center().y()
        else:
            y = min(max(y, min_y), max_y)
        return float(x), float(y)

    def _max_radii_for_center(self, x: float, y: float) -> tuple[float, float]:
        if self._pixmap_item is None:
            return float("inf"), float("inf")
        rect = self._pixmap_item.boundingRect()
        max_rx = max(MIN_NUCLEUS_RADIUS, min(x - rect.left(), rect.right() - x))
        max_ry = max(MIN_NUCLEUS_RADIUS, min(y - rect.top(), rect.bottom() - y))
        return float(max_rx), float(max_ry)

    def image_position_from_viewport_position(self, viewport_pos: QPoint | QPointF) -> QPointF | None:
        """Convert a viewport mouse position to original image coordinates.

        The scene may be zoomed or panned, but nuclei must be stored in
        original image pixels. Mapping through the pixmap item keeps the
        saved coordinates independent from the current view transform. Qt
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
