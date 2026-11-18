from typing import Callable

import cv2
import numpy as np
from PySide6.QtCore import Qt, QEvent, QPointF, QRectF, QTimer
from PySide6.QtGui import QImage, QPixmap, QPen, QColor
from PySide6.QtWidgets import (QGraphicsScene, QGraphicsRectItem, QTableWidgetItem,
                               QHeaderView, QMessageBox, QWidget)

from interface_module.ui_loader import loadUi
from logger import get_logger
from interface_module.translations import tr
from interface_module.shortcuts import ShortcutBinder
from project_module.project_manager import Project
from autodataset_module.photoshop import open_image

import sys
import os

log = get_logger("interface")



if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)
uis_path = os.path.join(base_path, "uis")

MIN_BBOX_SIZE = 5



def class_color(class_id: int, color_index: int) -> QColor:
    hsv_color = cv2.cvtColor(np.uint8([[[color_index * 30 % 180, 255, 255]]]), cv2.COLOR_HSV2RGB)[0][0]
    return QColor(int(hsv_color[0]), int(hsv_color[1]), int(hsv_color[2]))



class ImageEditWindow(QWidget):
    def __init__(self, project: Project, image_id: int, on_save: Callable, parent=None):
        super().__init__(parent)
        self.project = project
        self.on_save = on_save
        self.classes = project.get_all_classes_conf()
        self.loaded = False
        self.image_id = None
        self.image_data = None
        self.image = None
        self.sibling_ids: list[int] = []
        self.bboxes: list[list] = []
        self.rect_items: list[QGraphicsRectItem] = []
        self.selected_index: int | None = None
        self._mode = None
        self._press_scene_pos = None
        self._move_offset = None
        self._draw_start = None
        self._draw_target = None
        self._preview_item = None
        self._updating = False

        loadUi(os.path.join(uis_path, "editorwindow.ui"), self)
        self.setWindowTitle(tr("Редактор изображения"))
        self.resize(1100, 750)

        self.scene = QGraphicsScene(self)
        self.graphics_view.setScene(self.scene)
        self.graphics_view.setMouseTracking(True)
        self.graphics_view.viewport().installEventFilter(self)
        self.graphics_view.setCursor(Qt.CursorShape.CrossCursor)
        self.pixmap_item = None
        self.original_image_size = QPointF(0, 0)

        for class_data in self.classes:
            self.combo_main_class.addItem(f'{class_data["class_name"]} (id={class_data["id"]})', class_data["id"])
        self.combo_main_class.currentIndexChanged.connect(self.change_current_class)
        self.btn_add_row.clicked.connect(self.add_bbox_row)
        self.btn_remove_row.clicked.connect(self.remove_selected_bbox)
        self.btn_prev.clicked.connect(lambda: self.navigate(-1))
        self.btn_next.clicked.connect(lambda: self.navigate(1))
        self.table_annotations.itemChanged.connect(self.table_item_changed)
        self.table_annotations.currentCellChanged.connect(self.table_row_changed)
        self.table_annotations.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.load_image(image_id, save_current=False)
        self.shortcut_binder = ShortcutBinder(self)



    def class_name_by_id(self, class_id: int) -> str:
        for class_data in self.classes:
            if class_data["id"] == class_id:
                return class_data["class_name"]
        return str(class_id)



    def load_image(self, image_id: int, save_current: bool=True):
        if save_current and self.image_id is not None:
            self.save_annotation()
        image_data = self.project.get_image(image_id)
        if not image_data:
            log.warning("Image editor: image not found (id=%s)", image_id)
            return
        image_path = self.project.get_full_path("images", image_data["filename"])
        try:
            image = open_image(image_path)
        except Exception as e:
            log.error("✗ Image editor: cannot open image %s: %s", image_path, e)
            QMessageBox.warning(self, tr("Ошибка"), tr("Нет изображения"))
            return
        self.image_id = image_id
        self.image_data = image_data
        self.image = np.ascontiguousarray(image)
        self.bboxes = [list(bbox) for bbox in image_data["annotation"] or []]
        height, width = self.image.shape[:2]
        self.original_image_size = QPointF(width, height)
        qimage = QImage(self.image.data, width, height, width * 3, QImage.Format.Format_RGB888)
        self.scene.clear()
        self.rect_items, self.pixmap_item, self._preview_item = [], None, None
        self.pixmap_item = self.scene.addPixmap(QPixmap.fromImage(qimage))
        siblings = self.project.get_images(class_id=image_data["class_id"], type=image_data["type"])
        self.sibling_ids = [sibling["id"] for sibling in siblings]
        combo_index = self.combo_main_class.findData(image_data["class_id"])
        if combo_index >= 0:
            self.combo_main_class.setCurrentIndex(combo_index)
        position = self.sibling_ids.index(image_id) + 1 if image_id in self.sibling_ids else 1
        self.label_image_info.setText(
            f'{image_data["filename"]} • {width}x{height}px • {position}/{len(self.sibling_ids)} • '
            f'{self.class_name_by_id(image_data["class_id"])} • {image_data["type"]}')
        self.rebuild_annotations()
        self.selected_index = None
        self.loaded = True
        QTimer.singleShot(0, self.fit_image_to_view)
        log.info("▶ Image editor loaded: id=%s file=%s (%d bboxes)",
                 image_id, image_data["filename"], len(self.bboxes))



    def fit_image_to_view(self):
        if self.pixmap_item is not None:
            self.graphics_view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)



    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_image_to_view()



    def closeEvent(self, event):
        if self.image_id is not None:
            self.save_annotation()
            if self.on_save is not None:
                self.on_save()
        event.accept()



    def save_annotation(self):
        if not self.loaded or self.image_id is None:
            return
        annotation = [[int(bbox[0]), int(round(bbox[1])), int(round(bbox[2])),
                       int(round(bbox[3])), int(round(bbox[4]))] for bbox in self.bboxes]
        self.project.change_image(self.image_id, annotation=annotation)
        log.info("✓ Annotations saved: id=%s (%d bboxes)", self.image_id, len(annotation))



    def navigate(self, step: int):
        if not self.sibling_ids or self.image_id not in self.sibling_ids:
            return
        current_index = self.sibling_ids.index(self.image_id)
        next_id = self.sibling_ids[(current_index + step) % len(self.sibling_ids)]
        if next_id != self.image_id:
            self.load_image(next_id)



    def _class_color(self, index: int) -> QColor:
        class_id = int(self.bboxes[index][0])
        unique_ids = sorted(set(int(bbox[0]) for bbox in self.bboxes))
        return class_color(class_id, unique_ids.index(class_id))



    def rebuild_annotations(self):
        self._updating = True
        self.table_annotations.setRowCount(len(self.bboxes))
        for row, bbox in enumerate(self.bboxes):
            items = [self._table_item(self.class_name_by_id(bbox[0]), False),
                     self._table_item(str(int(round(bbox[1]))), True),
                     self._table_item(str(int(round(bbox[2]))), True),
                     self._table_item(str(int(round(bbox[3]))), True),
                     self._table_item(str(int(round(bbox[4]))), True)]
            for column, item in enumerate(items):
                self.table_annotations.setItem(row, column, item)
        self._updating = False
        self._rebuild_rects()
        self.apply_selection()



    @staticmethod
    def _table_item(text: str, editable: bool) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item



    def _rebuild_rects(self):
        for rect_item in self.rect_items:
            self.scene.removeItem(rect_item)
        self.rect_items = []
        if self._preview_item is not None:
            self.scene.removeItem(self._preview_item)
            self._preview_item = None
        for index, bbox in enumerate(self.bboxes):
            rect_item = QGraphicsRectItem(self._image_rect(index))
            rect_item.setPen(QPen(self._class_color(index), 2))
            rect_item.setZValue(1)
            self.scene.addItem(rect_item)
            self.rect_items.append(rect_item)



    def _image_rect(self, index: int) -> QRectF:
        x, y, w, h = self.bboxes[index][1:5]
        return QRectF(float(x), float(y), float(w), float(h))



    def apply_selection(self):
        for index, rect_item in enumerate(self.rect_items):
            color = self._class_color(index)
            pen = QPen(color, 3 if index == self.selected_index else 2)
            if index == self.selected_index:
                pen.setStyle(Qt.PenStyle.DashLine)
            rect_item.setPen(pen)
            rect_item.setZValue(2 if index == self.selected_index else 1)



    def _update_row(self, index: int):
        if not 0 <= index < len(self.bboxes):
            return
        self._updating = True
        bbox = self.bboxes[index]
        values = [self.class_name_by_id(bbox[0]), str(int(round(bbox[1]))), str(int(round(bbox[2]))),
                  str(int(round(bbox[3]))), str(int(round(bbox[4])))]
        for column, value in enumerate(values):
            self.table_annotations.item(index, column).setText(value)
        self._updating = False
        self.rect_items[index].setRect(self._image_rect(index))



    def select_bbox(self, index: int):
        self.selected_index = index
        self.apply_selection()
        if index is not None and 0 <= index < len(self.bboxes):
            self._updating = True
            self.table_annotations.setCurrentCell(index, 0)
            self._updating = False
            class_id = int(self.bboxes[index][0])
            combo_index = self.combo_main_class.findData(class_id)
            if combo_index >= 0:
                self.combo_main_class.setCurrentIndex(combo_index)



    def change_current_class(self):
        class_id = self.combo_main_class.currentData()
        if class_id is None or self.selected_index is None:
            return
        if not 0 <= self.selected_index < len(self.bboxes):
            return
        self.bboxes[self.selected_index][0] = class_id
        self.rect_items[self.selected_index].setPen(QPen(self._class_color(self.selected_index), 3))
        self._update_row(self.selected_index)
        self.apply_selection()



    def add_bbox_row(self):
        if self.original_image_size.isNull() or self.combo_main_class.currentData() is None:
            return
        class_id = self.combo_main_class.currentData()
        width, height = int(self.original_image_size.x()), int(self.original_image_size.y())
        x, y, w, h = width // 3, height // 3, max(MIN_BBOX_SIZE, width // 3), max(MIN_BBOX_SIZE, height // 3)
        self.bboxes.append([class_id, x, y, w, h])
        self.rebuild_annotations()
        self.select_bbox(len(self.bboxes) - 1)



    def remove_selected_bbox(self):
        if self.selected_index is None or not 0 <= self.selected_index < len(self.bboxes):
            return
        self.bboxes.pop(self.selected_index)
        self.selected_index = None
        self.rebuild_annotations()



    def table_row_changed(self, current_row: int, *_):
        if self._updating:
            return
        self.selected_index = current_row if 0 <= current_row < len(self.bboxes) else None
        self.apply_selection()
        if self.selected_index is not None:
            class_id = int(self.bboxes[self.selected_index][0])
            combo_index = self.combo_main_class.findData(class_id)
            if combo_index >= 0:
                self.combo_main_class.setCurrentIndex(combo_index)



    def table_item_changed(self, item: QTableWidgetItem):
        if self._updating or item.column() == 0:
            return
        index = item.row()
        if not 0 <= index < len(self.bboxes):
            return
        try:
            value = int(item.text())
        except ValueError:
            self._update_row(index)
            return
        width, height = int(self.original_image_size.x()), int(self.original_image_size.y())
        value = max(0, value)
        if item.column() in (3, 4):
            value = max(MIN_BBOX_SIZE, value)
        if item.column() == 1:
            value = min(value, width - MIN_BBOX_SIZE)
        elif item.column() == 2:
            value = min(value, height - MIN_BBOX_SIZE)
        self.bboxes[index][item.column()] = value
        self._update_row(index)



    def to_image_pos(self, scene_pos: QPointF) -> QPointF | None:
        if self.pixmap_item is None or self.original_image_size.isNull():
            return None
        pixmap_rect = self.pixmap_item.boundingRect()
        if not pixmap_rect.contains(scene_pos):
            return None
        scale_x = self.original_image_size.x() / pixmap_rect.width()
        scale_y = self.original_image_size.y() / pixmap_rect.height()
        return QPointF((scene_pos.x() - pixmap_rect.x()) * scale_x,
                       (scene_pos.y() - pixmap_rect.y()) * scale_y)



    def clamp_pos(self, pos: QPointF) -> QPointF:
        return QPointF(min(max(pos.x(), 0), self.original_image_size.x()),
                       min(max(pos.y(), 0), self.original_image_size.y()))



    def rect_at_scene(self, scene_pos: QPointF) -> int | None:
        for index in range(len(self.rect_items) - 1, -1, -1):
            if self.rect_items[index].contains(scene_pos):
                return index
        return None



    def eventFilter(self, watched, event):
        if watched is self.graphics_view.viewport():
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.handle_mouse_press(event)
                return True
            elif event_type == QEvent.Type.MouseMove:
                self.handle_mouse_move(event)
                return True
            elif event_type == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self.handle_mouse_release(event)
                return True
        return super().eventFilter(watched, event)



    def handle_mouse_press(self, event):
        if self.pixmap_item is None:
            return
        scene_pos = self.graphics_view.mapToScene(event.position().toPoint())
        self._press_scene_pos = scene_pos
        index = self.rect_at_scene(scene_pos)
        if self.radio_move.isChecked():
            image_pos = self.to_image_pos(scene_pos)
            if image_pos is None or index is None:
                self.select_bbox(index)
                self._mode = None
                return
            self.select_bbox(index)
            self._mode = "move"
            self._move_offset = image_pos - QPointF(self.bboxes[index][1], self.bboxes[index][2])
        else:
            self._mode = "draw"
            self._draw_start = self.clamp_pos(self.to_image_pos(scene_pos) or self._draw_start or QPointF(0, 0))
            self._draw_target = index



    def handle_mouse_move(self, event):
        if self._mode not in ("move", "draw") or self.pixmap_item is None:
            return
        scene_pos = self.graphics_view.mapToScene(event.position().toPoint())
        image_pos = self.to_image_pos(scene_pos)
        if image_pos is None:
            return
        if self._mode == "move" and self.selected_index is not None:
            new_pos = self.clamp_pos(image_pos - self._move_offset)
            width, height = int(self.original_image_size.x()), int(self.original_image_size.y())
            bbox = self.bboxes[self.selected_index]
            bbox[1] = min(new_pos.x(), width - bbox[3])
            bbox[2] = min(new_pos.y(), height - bbox[4])
            self._update_row(self.selected_index)
        elif self._mode == "draw" and self._draw_start is not None:
            current = self.clamp_pos(image_pos)
            rect = QRectF(self._draw_start, current).normalized()
            if self._preview_item is None:
                self._preview_item = QGraphicsRectItem(rect)
                self._preview_item.setPen(QPen(QColor(255, 255, 255), 2, Qt.PenStyle.DashLine))
                self._preview_item.setZValue(3)
                self.scene.addItem(self._preview_item)
            else:
                self._preview_item.setRect(rect)



    def handle_mouse_release(self, event):
        if self._mode == "draw" and self._draw_start is not None:
            scene_pos = self.graphics_view.mapToScene(event.position().toPoint())
            image_pos = self.to_image_pos(scene_pos)
            if image_pos is not None:
                rect = QRectF(self._draw_start, self.clamp_pos(image_pos)).normalized()
                if rect.width() >= MIN_BBOX_SIZE and rect.height() >= MIN_BBOX_SIZE:
                    class_id = (self.bboxes[self._draw_target][0]
                                if self._draw_target is not None else self.combo_main_class.currentData())
                    if self._draw_target is not None:
                        self.bboxes[self._draw_target][1:5] = [rect.x(), rect.y(), rect.width(), rect.height()]
                        self.rebuild_annotations()
                        self.select_bbox(self._draw_target)
                    elif class_id is not None:
                        self.bboxes.append([class_id, rect.x(), rect.y(), rect.width(), rect.height()])
                        self.rebuild_annotations()
                        self.select_bbox(len(self.bboxes) - 1)
        if self._preview_item is not None:
            self.scene.removeItem(self._preview_item)
            self._preview_item = None
        self._mode = None
        self._draw_start = None
        self._draw_target = None
