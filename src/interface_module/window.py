from PySide6.QtWidgets import (QMainWindow, QWidget, QHeaderView, QTabWidget,
                             QTableWidgetItem, QFileDialog, QVBoxLayout, QMessageBox,
                             QApplication)
from PySide6.QtGui import QImage, QPixmap, QDrag
from PySide6.QtCore import QTimer, Qt, QEvent, QMimeData, QUrl, QPoint
from datetime import datetime
from typing import Callable
import numpy as np
import sys
import os
import json

from interface_module.ui_loader import loadUi
from logger import get_logger
from interface_module.translations import tr
from interface_module.shortcuts import ShortcutBinder
from pcfuncs import CAN_EMBED_PROGRAMS

try:
    from .embedded_program_qt import EmbeddedProgramWidget
except ModuleNotFoundError:
    EmbeddedProgramWidget = None


if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)
uis_path = os.path.join(base_path, "uis")

log = get_logger("interface")

MIME_OBJECT_CARD = "application/x-maclearn-object-card"
MIME_CLASS_FIELD = "application/x-maclearn-class-field"
MIME_CARD_DATA = "application/x-maclearn-card-data"



class InformationWidget(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        ui_file = os.path.join(uis_path, "widgets", "information.ui")
        self.ui = loadUi(ui_file, self)
        self.ui.label_title.setText(title)
        self.table = self.ui.table_info
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    def add_information(self, data: dict):
        self.table.setRowCount(len(data))
        for row, (key, value) in enumerate(data.items()):
            if isinstance(value, bool):
                value = "✅ Да" if value else "❌ Нет"
            elif value is None:
                value = "—"
            else:
                value = str(value)
            key_item = QTableWidgetItem(str(key))
            value_item = QTableWidgetItem(value)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, key_item)
            self.table.setItem(row, 1, value_item)
        self._adjust_table_height()

    def _adjust_table_height(self):
        if self.table.rowCount() == 0:
            return
        header_height = self.table.horizontalHeader().height()
        rows_height = sum([self.table.rowHeight(row) for row in range(self.table.rowCount())])
        horizontal_header_height = 0
        if self.table.horizontalHeader().isVisible():
            horizontal_header_height = self.table.horizontalHeader().height()
        total_height = header_height + rows_height + horizontal_header_height + 10
        self.table.setMinimumHeight(total_height)
        self.table.setMaximumHeight(total_height)
        self.updateGeometry()

    def clear(self):
        self.table.setRowCount(0)
        self.table.setMinimumHeight(0)
        self.table.setMaximumHeight(16777215)


class StatisticsWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        ui_file = os.path.join(uis_path, "statisticswindow.ui")
        self.ui = loadUi(ui_file, self)
        self.stats_layout = self.ui.stats_layout
        self.ui.btn_close.clicked.connect(self.close)
        self.widgets = []
        self.shortcut_binder = ShortcutBinder(self)

    def add_information(self, title: str, information: dict):
        widget = InformationWidget(title, self)
        widget.add_information(information)
        self.stats_layout.addWidget(widget)
        self.widgets.append(widget)

    def add_information_batch(self, data: dict):
        for title, info in data.items():
            self.add_information(title, info)

    def clear_all(self):
        for widget in self.widgets:
            widget.deleteLater()
        self.widgets.clear()



class ObjectCardWidget(QWidget):
    drag_instance: "ObjectCardWidget" = None

    def __init__(self):
        super().__init__()
        self.field: ClassFieldWidget = None
        self.movable = True
        self.image_id = None
        self.file_path = None
        self._click_handler = None
        self._drag_start_pos = None
        self._drag_pressed_pos = None
        self._drag_started = False

    def initUI(self, object_name: str=None, object_image: str | np.ndarray=None,
               name_enabled: bool=True, click_image: Callable=None):
        loadUi(os.path.join(uis_path, "widgets", "object_card.ui"), self)
        self.object_image.my_image_path = ""
        if object_image is not None:
            self.update_object_image(object_image)
        self._click_handler = self.object_image_click if not click_image else click_image
        self.object_image.installEventFilter(self)
        if object_name:
            self.object_name.setText(object_name)
        self.object_name.setEnabled(name_enabled)
        self.object_delete.clicked.connect(
            lambda: self.delete_object())



    def eventFilter(self, watched, event):
        if watched is self.object_image:
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_start_pos = event.position().toPoint()
                self._drag_pressed_pos = self.object_image.mapTo(self, self._drag_start_pos)
                self._drag_started = False
                return True
            elif event_type == QEvent.Type.MouseMove and self._drag_start_pos is not None:
                if (event.position().toPoint() - self._drag_start_pos).manhattanLength() >= QApplication.startDragDistance():
                    self._drag_start_pos = None
                    self._drag_started = True
                    self.start_drag()
                return True
            elif event_type == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self._drag_start_pos = None
                if not self._drag_started and self._click_handler is not None:
                    self._click_handler(event)
                return True
        return super().eventFilter(watched, event)



    def start_drag(self):
        ObjectCardWidget.drag_instance = self
        mime_data = QMimeData()
        mime_data.setData(MIME_OBJECT_CARD, b"1")
        image_path = self.file_path if isinstance(self.file_path, str) and self.file_path \
            else self.object_image.my_image_path
        if isinstance(image_path, str) and image_path and os.path.isfile(image_path):
            mime_data.setUrls([QUrl.fromLocalFile(image_path)])
        payload = {}
        if self.image_id is not None:
            payload["image_id"] = self.image_id
        if isinstance(image_path, str) and image_path:
            payload["file"] = image_path
        if payload:
            mime_data.setData(MIME_CARD_DATA, json.dumps(payload).encode())
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag_pixmap = self.grab()
        drag.setPixmap(drag_pixmap)
        drag.setHotSpot(self._drag_pressed_pos if self._drag_pressed_pos is not None
                        else QPoint(drag_pixmap.width() // 2, drag_pixmap.height() // 2))
        drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction, Qt.DropAction.MoveAction)
        ObjectCardWidget.drag_instance = None



    @staticmethod
    def _mime_file_paths(mime_data: QMimeData) -> list[str]:
        paths = [url.toLocalFile() for url in mime_data.urls() if url.isLocalFile()]
        if mime_data.hasFormat(MIME_CARD_DATA):
            try:
                file_path = json.loads(bytes(mime_data.data(MIME_CARD_DATA))).get("file")
            except ValueError:
                file_path = None
            if isinstance(file_path, str) and file_path and file_path not in paths:
                paths.append(file_path)
        return paths



    def _accepts_urls(self, mime_data: QMimeData) -> bool:
        if mime_data.hasFormat(MIME_OBJECT_CARD) and ObjectCardWidget.drag_instance is not None:
            return False
        if mime_data.hasFormat(MIME_CARD_DATA):
            return True
        if not mime_data.hasUrls():
            return False
        return any(url.isLocalFile() for url in mime_data.urls())



    def dragEnterEvent(self, event):
        if self._accepts_urls(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()



    def dragMoveEvent(self, event):
        if self._accepts_urls(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()



    def dropEvent(self, event):
        if not self._accepts_urls(event.mimeData()):
            event.ignore()
            return
        event.acceptProposedAction()
        for image_path in self._mime_file_paths(event.mimeData()):
            if os.path.isfile(image_path) and self.update_object_image(image_path):
                log.info("Subclass image updated by drop: %s -> %s",
                         image_path, self.object_name.text())
                return

    def delete_object(self):
        self.setParent(None)
        self.deleteLater()


    def update_object_image(self, image: str | np.ndarray | bool=None) -> bool:
        try:
            if isinstance(image, np.ndarray) and image.size>0:
                qimage = QImage(
                    image.data, image.shape[1], 
                    image.shape[0], image.shape[1]*3,
                    QImage.Format.Format_RGB888)
                self.object_image.my_image_path = None
            elif isinstance(image, str) or image is None:
                qimage = QImage(image)
                self.object_image.my_image_path = image
            else:
                raise ValueError(f"param image can be str, np.ndarray or None. Get {type(image)}")
            pixmap = QPixmap.fromImage(qimage).scaled(
                self.object_image.parent().maximumWidth(),
                self.object_image.parent().maximumHeight(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.object_image.setPixmap(pixmap)
            self.object_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return True
        except Exception as e:
            self.object_image.setText(f"Ошибка: {e}")
            return False

    def object_image_click(self, event):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Images (*.png *.jpg)")
        path, ok = file_dialog.getOpenFileName()
        if ok:
            self.update_object_image(path)



class ClassFieldWidget(QWidget):
    drag_instance: "ClassFieldWidget" = None

    def __init__(self):
        super().__init__()
        self.objects: list[ObjectCardWidget] = []
        self.on_object_drop: Callable | None = None
        self.on_files_drop: Callable | None = None
        self.on_card_data_drop: Callable | None = None
        self.reorderable = False
        self._class_drag_start = None

    def initUI(self, class_name: str=None, enabled: bool=True,
               import_and_export_buttons: bool=True, delete_ann_button: bool=True, name_enabled: bool=True):
        loadUi(os.path.join(uis_path, "widgets", "class_field.ui"), self)
        if not import_and_export_buttons:
            self.class_export_files.deleteLater()
            self.class_import_files.deleteLater()
        if delete_ann_button:
            self.class_delete_annotations.deleteLater()
        self.setAcceptDrops(True)
        self.class_checkbox.stateChanged.connect(self.show_class)
        self.class_delete.clicked.connect(self.delete_class)
        self.class_add_object.clicked.connect(lambda: (self.add_object().setVisible(True), self.update_layout()))
        self.class_checkbox.setChecked(enabled)
        if class_name:
            self.class_name.setText(class_name)
        self.name_enabled = name_enabled
        self.show_class()

    def show_class(self, enabled: bool=None):
        if enabled is None:
            enabled = self.class_checkbox.isChecked()
        else:
            self.class_checkbox.setChecked(enabled)
        self.class_name.setEnabled(self.name_enabled)
        self.class_add_object.setEnabled(enabled)
        for object in self.objects:
            object.setEnabled(enabled)


    def delete_class(self):
        for object in self.objects:
            self.delete_object(object)
        self.objects.clear()
        self.setParent(None)
        self.deleteLater()

    def add_object(self, object_name: str=None, object_image: str | np.ndarray=None,
                   name_enabled: bool=True, click_image: Callable=None) -> ObjectCardWidget:
        object_card = ObjectCardWidget()
        object_card.initUI(object_name, object_image, name_enabled, click_image)
        object_card.field = self
        object_card.setAcceptDrops(self.on_files_drop is None)
        object_card.object_delete.clicked.connect(
            lambda: (self.delete_object(object_card), self.update_layout()))
        self.objects.append(object_card)
        return object_card



    def move_object(self, object_widget: ObjectCardWidget):
        if object_widget is None or object_widget.field is self:
            return
        same_object = self.get_object(object_widget.object_name.text())
        old_field = object_widget.field
        if old_field is not None and object_widget in old_field.objects:
            old_field.objects.remove(object_widget)
            old_field.update_layout()
        if isinstance(same_object, ObjectCardWidget):
            object_widget.delete_object()
            log.info("Subclass merged with existing: %s -> class=%s",
                     object_widget.object_name.text(), self.class_name.text())
            return
        object_widget.field = self
        if object_widget not in self.objects:
            self.objects.append(object_widget)
        self.class_grid_layout.addWidget(object_widget)
        self.update_layout()
        log.info("Object moved to class: object=%s class=%s",
                 object_widget.object_name.text(), self.class_name.text())



    def _accepted_mime(self, mime_data: QMimeData) -> bool:
        if mime_data.hasFormat(MIME_CLASS_FIELD):
            return self.reorderable and ClassFieldWidget.drag_instance is not None
        if mime_data.hasFormat(MIME_OBJECT_CARD):
            card = ObjectCardWidget.drag_instance
            if card is not None:
                return card.field is not self and (card.movable or self.on_object_drop is not None)
            return mime_data.hasFormat(MIME_CARD_DATA) or self.on_files_drop is not None
        return mime_data.hasUrls() and any(url.isLocalFile() for url in mime_data.urls())



    def dragEnterEvent(self, event):
        if self._accepted_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()



    def dragMoveEvent(self, event):
        if self._accepted_mime(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()



    def dropEvent(self, event):
        mime_data = event.mimeData()
        event.ignore()
        if not self._accepted_mime(mime_data):
            return
        if mime_data.hasFormat(MIME_CLASS_FIELD):
            source_field = ClassFieldWidget.drag_instance
            if source_field is None or source_field is self:
                return
            event.acceptProposedAction()
            overview = self.parent()
            while overview is not None and not isinstance(overview, OverviewClassWidget):
                overview = overview.parent()
            if isinstance(overview, OverviewClassWidget):
                overview.reorder_field(source_field, self)
            return
        if mime_data.hasFormat(MIME_OBJECT_CARD):
            card = ObjectCardWidget.drag_instance
            if card is not None:
                if card.field is self or not (card.movable or self.on_object_drop is not None):
                    return
                event.acceptProposedAction()
                if self.on_object_drop is not None:
                    self.on_object_drop(card, self)
                else:
                    self.move_object(card)
                return
            if mime_data.hasFormat(MIME_CARD_DATA) and self.on_card_data_drop is not None:
                try:
                    payload = json.loads(bytes(mime_data.data(MIME_CARD_DATA)))
                except ValueError:
                    payload = {}
                event.acceptProposedAction()
                self.on_card_data_drop(payload, self)
                return
        local_files = [url.toLocalFile() for url in mime_data.urls() if url.isLocalFile()]
        if not local_files:
            return
        event.acceptProposedAction()
        if self.on_files_drop is not None:
            self.on_files_drop(local_files, self)
            return
        for file_path in local_files:
            self.add_object(os.path.basename(file_path), file_path)
        self.update_layout()
        log.info("Objects created from dropped files: %d -> class=%s",
                 len(local_files), self.class_name.text())



    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.reorderable:
            self._class_drag_start = event.position().toPoint()
        super().mousePressEvent(event)



    def mouseMoveEvent(self, event):
        if self._class_drag_start is not None:
            if (event.position().toPoint() - self._class_drag_start).manhattanLength() >= QApplication.startDragDistance():
                self._class_drag_start = None
                self.start_class_drag()
        super().mouseMoveEvent(event)



    def start_class_drag(self):
        ClassFieldWidget.drag_instance = self
        mime_data = QMimeData()
        mime_data.setData(MIME_CLASS_FIELD, b"1")
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.setPixmap(self.grab())
        drag.exec(Qt.DropAction.MoveAction)
        ClassFieldWidget.drag_instance = None

    def delete_object(self, object_widget: ObjectCardWidget, user_call: bool=False):
        if object_widget in self.objects:
            self.objects.remove(object_widget)
            object_widget.delete_object()

    def get_object(self, object_name: str=None) -> bool | ObjectCardWidget:
        for object in self.objects:
            if object.object_name.text()==object_name:
                return object
        return False


    def update_layout(self):
        objects = list(filter(lambda o: o.isVisible(), self.objects))
        if not objects:
            if not self.objects:
                return
            objects = self.objects

        all_widgets = objects + [self.class_add_object]
        widget_width = all_widgets[0].minimumWidth() if all_widgets[0].minimumWidth() > 0 else 100
        max_subclasses_per_row = max(1, (self.width() - 10) // (widget_width + 10))

        for i, widget in enumerate(all_widgets):
            row, col = i // max_subclasses_per_row, i % max_subclasses_per_row
            current_index = self.class_grid_layout.indexOf(widget)
            if current_index == -1:
                self.class_grid_layout.addWidget(widget, row, col)
            else:
                current_row, current_col, row_span, col_span = self.class_grid_layout.getItemPosition(current_index)
                if current_row != row or current_col != col:
                    self.class_grid_layout.addWidget(widget, row, col)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_layout()



class OverviewClassWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.fields: list[ClassFieldWidget] = []

    def initUI(self, class_name: str=None):
        loadUi(os.path.join(uis_path, "widgets", "overview_class.ui"), self)
        if class_name:
            self.overview_group.setTitle(class_name)
        self.tab_bar.currentChanged.connect(self.scroll_to_field)
        self.lineEdit_search.textChanged.connect(self.search_update)
        self.overview_scroll_area.verticalScrollBar().valueChanged.connect(self.update_tab_selection_from_scroll)


    def add_field(self, field_widget: ClassFieldWidget, field_name: str):
        self.overview_vertical_layout.addWidget(field_widget)
        self.fields.append(field_widget)
        self.tab_bar.setTabData(self.tab_bar.addTab(field_name), field_widget)
        field_widget.class_name.textChanged.connect(lambda name: self.update_tab_name(field_widget, name))

    def update_tab_name(self, field_widget: ClassFieldWidget, new_name: str):
        for i in range(self.tab_bar.count()):
            if self.tab_bar.tabData(i) is field_widget:
                self.tab_bar.setTabText(i, new_name)
                break

    def remove_field(self, field_widget: ClassFieldWidget):
        if field_widget in self.fields:
            for i in range(self.tab_bar.count()):
                if self.tab_bar.tabData(i) is field_widget:
                    self.tab_bar.removeTab(i)
                    break
            self.fields.remove(field_widget)
            if self.overview_vertical_layout:
                self.overview_vertical_layout.removeWidget(field_widget)
            field_widget.delete_class()



    def reorder_field(self, dragged_field: ClassFieldWidget, target_field: ClassFieldWidget):
        if dragged_field is target_field:
            return
        if dragged_field not in self.fields or target_field not in self.fields:
            return
        self.fields.remove(dragged_field)
        insert_index = self.fields.index(target_field)
        self.fields.insert(insert_index, dragged_field)
        self.overview_vertical_layout.removeWidget(dragged_field)
        self.overview_vertical_layout.insertWidget(insert_index, dragged_field)
        self.tab_bar.blockSignals(True)
        for i in range(self.tab_bar.count() - 1, -1, -1):
            self.tab_bar.removeTab(i)
        for field_widget in self.fields:
            self.tab_bar.setTabData(self.tab_bar.addTab(field_widget.class_name.text()), field_widget)
        self.tab_bar.blockSignals(False)
        log.info("Class reordered: %s -> position %d", dragged_field.class_name.text(), insert_index)


    def search_update(self):
        search_text = self.lineEdit_search.text().lower()
        for field in self.fields:
            for object in field.objects:
                if search_text in object.object_name.text().lower() or not search_text:
                    object.show()
                else:
                    object.hide()
        self.update_all_fields_layouts()

    def update_all_fields_layouts(self):
        for field_widget in self.fields:
            field_widget.update_layout()

    def scroll_to_field(self, index: int):
        def _scroll_to_widget(widget, scroll_area):
            pos_in_contents = widget.mapTo(scroll_area.widget(), widget.rect().topLeft())
            scroll_area.verticalScrollBar().setValue(pos_in_contents.y())
        if 0<=index<len(self.fields):
            QTimer.singleShot(0, lambda: _scroll_to_widget(
                self.fields[index], self.overview_scroll_area))

    def update_tab_selection_from_scroll(self):
        scroll_pos = self.overview_scroll_area.verticalScrollBar().value()
        viewport_height = self.overview_scroll_area.viewport().height()
        best_index, best_visibility = -1, -1
        for i, field_widget in enumerate(self.fields):
            if not field_widget.isVisible():
                continue
            widget_y = field_widget.mapTo(self.overview_scroll_area.widget(), field_widget.rect().topLeft()).y()
            visible_bottom = min(widget_y+field_widget.height(), scroll_pos+viewport_height)
            visible_height = max(0, visible_bottom - max(widget_y, scroll_pos))
            if visible_height>best_visibility:
                best_visibility, best_index = visible_height, i
        if best_index!=-1:
            self.tab_bar.blockSignals(True)
            self.tab_bar.setCurrentIndex(best_index)
            self.tab_bar.blockSignals(False)


    def get_field_by_name(self, field_name: str) -> ClassFieldWidget | bool:
        for field_widget in self.fields:
            if field_widget.class_name.text()==field_name:
                return field_widget
        return False



class MainWindowUI(QMainWindow):
    def __init__(self):
        super().__init__()

    def initUI(self):
        loadUi(os.path.join(uis_path, "mainwindow.ui"), self)
        from version import get_app_version
        self.setWindowTitle(f"{self.windowTitle()} {get_app_version()}")
        self.project_initUI()
        self.dataset_initUI()
        self.autodataset_initUI()

    def project_initUI(self):
        self.project_tab = loadUi(os.path.join(uis_path, "tabs", "project_tab.ui"))
        self.tabWidget.addTab(self.project_tab, tr("Проект"))
        self.project_tab.project_overview = OverviewClassWidget()
        self.project_tab.project_overview.initUI(tr("Классы объектов"))
        self.project_tab.verticalLayout_2.insertWidget(0, self.project_tab.project_overview)
        self.project_tab.btn_add_class.clicked.connect(self.project_add_class)
        self.project_resize_timer = QTimer()
        self.project_resize_timer.setSingleShot(True)
        self.project_resize_timer.timeout.connect(self.project_tab.project_overview.update_all_fields_layouts)

    def project_add_class(self, class_name: str = None, enabled: bool = True) -> ClassFieldWidget:
        class_name = class_name or f"{tr('Класс')} {len(self.project_tab.project_overview.fields) + 1}"
        class_widget = ClassFieldWidget()
        class_widget.initUI(class_name, enabled, False)
        class_widget.reorderable = True
        self.project_tab.project_overview.add_field(class_widget, class_name)
        class_widget.class_delete.clicked.connect(
            lambda: self.project_tab.project_overview.remove_field(class_widget))
        log.info("Class added to project: %s", class_name)
        return class_widget


    def dataset_initUI(self):
        self.dataset_tab = loadUi(os.path.join(uis_path, "tabs", "dataset_tab.ui"))
        self.tabWidget.addTab(self.dataset_tab, tr("Датасет"))
        self.dataset_tab.classes_tabs = {}
        self.dataset_resize_timer = QTimer()
        self.dataset_resize_timer.setSingleShot(True)
        self.dataset_resize_timer.timeout.connect(self.dataset_update_all_class_layouts)
        self.dataset_tab.tab_bar.currentChanged.connect(self.dataset_on_tab_changed)
        self.dataset_tab.tab_bar.setAcceptDrops(True)
        self.dataset_tab.tab_bar.installEventFilter(self)
        self._hover_tab_index = -1
        self._class_tab_switch_timer = QTimer(self.dataset_tab.tab_bar)
        self._class_tab_switch_timer.setSingleShot(True)
        self._class_tab_switch_timer.setInterval(400)
        self._class_tab_switch_timer.timeout.connect(self._activate_hovered_class_tab)



    def _activate_hovered_class_tab(self):
        index = self._hover_tab_index
        if index < 0 or index == self.dataset_tab.tab_bar.currentIndex():
            return
        self.tabWidget.setCurrentWidget(self.dataset_tab)
        self.dataset_tab.tab_bar.setCurrentIndex(index)
        log.info("Class tab activated by image drag hover: %s", self.dataset_tab.tab_bar.tabText(index))



    def eventFilter(self, watched, event):
        if watched is self.dataset_tab.tab_bar:
            event_type = event.type()
            if event_type in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                card = ObjectCardWidget.drag_instance
                has_files = any(url.isLocalFile() for url in event.mimeData().urls())
                if (card is not None and card.image_id is not None) or has_files:
                    event.acceptProposedAction()
                    if event_type == QEvent.Type.DragMove:
                        index = self.dataset_tab.tab_bar.tabAt(event.position().toPoint())
                        self._hover_tab_index = index
                        if card is not None and card.image_id is not None and index >= 0 \
                                and index != self.dataset_tab.tab_bar.currentIndex():
                            self._class_tab_switch_timer.start()
                        else:
                            self._class_tab_switch_timer.stop()
                else:
                    event.ignore()
                    self._class_tab_switch_timer.stop()
                return True
            if event_type == QEvent.Type.Drop:
                self._class_tab_switch_timer.stop()
                self.dataset_tab_drop(event)
                return True
            if event_type == QEvent.Type.DragLeave:
                self._class_tab_switch_timer.stop()
                self._hover_tab_index = -1
        return super().eventFilter(watched, event)



    def dataset_tab_drop(self, event):
        index = self.dataset_tab.tab_bar.tabAt(event.position().toPoint())
        if index < 0:
            return
        target_class_name = self.dataset_tab.tab_bar.tabText(index)
        card = ObjectCardWidget.drag_instance
        event.acceptProposedAction()
        if card is not None and card.image_id is not None:
            current_overview = card.field.parent() if card.field else None
            while current_overview is not None and not isinstance(current_overview, OverviewClassWidget):
                current_overview = current_overview.parent()
            current_class_name = (self.get_overview_class_name_in_dataset(current_overview)
                                  if isinstance(current_overview, OverviewClassWidget) else None)
            if current_class_name != target_class_name and getattr(self.dataset_tab, "tab_drop_move", None):
                self.dataset_tab.tab_drop_move(card, target_class_name)
                return
            return
        local_files = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self.tabWidget.setCurrentWidget(self.dataset_tab)
        self.dataset_tab.tab_bar.setCurrentIndex(index)
        if local_files and getattr(self.dataset_tab, "tab_drop_files", None):
            self.dataset_tab.tab_drop_files(local_files, target_class_name)
            return
        log.info("Class tab opened by drop: %s", target_class_name)

    def dataset_on_tab_changed(self, index):
        if index>=0:
            class_name = self.dataset_tab.tab_bar.tabText(index)
            if class_name in self.dataset_tab.classes_tabs:
                for widget in self.dataset_tab.classes_tabs.values():
                    widget.hide()
                selected_widget = self.dataset_tab.classes_tabs[class_name]
                selected_widget.show()
                layout = self.dataset_tab.content_widget.layout()
                if selected_widget.parent()!=self.dataset_tab.content_widget:
                    layout.addWidget(selected_widget)
                selected_widget.update_all_fields_layouts()

    def dataset_add_class(self, class_name: str=None) -> OverviewClassWidget:
        overview_widget = OverviewClassWidget()
        overview_widget.initUI(class_name)
        self.dataset_tab.classes_tabs[class_name] = overview_widget
        if self.dataset_tab.tab_bar.count()==0:
            self.dataset_tab.content_widget.layout().addWidget(overview_widget)
            overview_widget.show()
        else:
            overview_widget.hide()
        self.dataset_tab.tab_bar.addTab(class_name)
        log.info("Class added to dataset view: %s", class_name)
        return overview_widget

    def dataset_delete_class(self, overview_widget: OverviewClassWidget, user_call: bool=True) -> bool:
        if user_call:
            reply = QMessageBox.question(
                self, tr("Удаление класса"),
                tr("Вы точно хотите удалить класс? Все изображения которые относились к нему также будут удалены."),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if (not user_call) or reply==QMessageBox.StandardButton.Yes:
            class_name_to_remove = self.get_overview_class_name_in_dataset(overview_widget)
            if class_name_to_remove:
                for i in range(self.dataset_tab.tab_bar.count()):
                    if self.dataset_tab.tab_bar.tabText(i)==class_name_to_remove:
                        self.dataset_tab.tab_bar.removeTab(i)
                        break
                self.dataset_tab.content_widget.layout().removeWidget(overview_widget)
                overview_widget.deleteLater()
                del self.dataset_tab.classes_tabs[class_name_to_remove]
                return True
        return False

    def dataset_add_class_field(self, class_name: str, field_name: str, enabled: bool=True) -> ClassFieldWidget:
        field_widget = ClassFieldWidget()
        field_widget.initUI(field_name, enabled, True, False, False)
        field_widget.class_delete.clicked.disconnect()
        field_widget.class_delete.clicked.connect(
            lambda: self.dataset_delete_class_field_widget(field_widget))
        self.dataset_tab.classes_tabs[class_name].add_field(field_widget, field_name)
        return field_widget

    def dataset_delete_class_field_widget(self, field_widget: ClassFieldWidget, user_call: bool=True) -> bool:
        if user_call:
            reply = QMessageBox.question(
                self, tr("Удаление класса"), tr("Вы точно хотите удалить этот класс? Все связанные с ним данные будут удалены."),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if (not user_call) or reply == QMessageBox.StandardButton.Yes:
            field_widget.delete_class()
            class_widget = None
            for widget in self.dataset_tab.classes_tabs.values():
                if field_widget in widget.fields:
                    class_widget = widget
                    break
            if class_widget:
                class_widget.remove_field(field_widget)
                field_widget.deleteLater()
            return True
        return False

    def get_class_field_in_dataset(self, class_name: str, field_name: str) -> bool | ClassFieldWidget:
        class_tab = self.dataset_tab.classes_tabs.get(class_name)
        if class_tab:
            return class_tab.get_field_by_name(field_name)
        return False

    def get_overview_class_name_in_dataset(self, overview_class_widget: OverviewClassWidget) -> bool | str:
        for cur_class_name, widget in self.dataset_tab.classes_tabs.items():
            if widget==overview_class_widget:
                return cur_class_name

    def dataset_update_all_class_layouts(self):
        for class_overview in self.dataset_tab.classes_tabs.values():
            class_overview.update_all_fields_layouts()


    def autodataset_initUI(self):
        self.autodataset_tab = QWidget()
        self.autodataset_tab.tab_widget = QTabWidget()
        # Вкладки нужны только когда Chrome встраивается в окно приложения (не headless и
        # доступно встраивание экрана). При единственной вкладке полоса вкладок скрывается
        # сама, а рамка и отступы панели убираются, чтобы "Работа" занимала всё пространство.
        self.autodataset_tab.tab_widget.setTabBarAutoHide(True)
        self.autodataset_tab.tab_widget.setDocumentMode(True)
        self.autodataset_tab.tab_widget.setStyleSheet(
            "QTabWidget { padding: 0px; } "
            "QTabWidget::pane, QTabWidget::pane:selected { border: none; background: transparent; }")
        self.autodataset_tab.work_tab = loadUi(os.path.join(uis_path, "tabs", "autodataset_tab.ui"))
        self.autodataset_tab.setLayout(QVBoxLayout())
        self.autodataset_tab.layout().setContentsMargins(0, 0, 0, 0)
        self.autodataset_tab.layout().setSpacing(0)
        self.autodataset_tab.tab_widget.addTab(self.autodataset_tab.work_tab, tr("Работа"))
        self.autodataset_tab.layout().addWidget(self.autodataset_tab.tab_widget)
        self.tabWidget.addTab(self.autodataset_tab, tr("Автодатасет"))
        self.autodataset_setup_interface()
        self.setup_autodataset()

    def setup_autodataset(self):
        self.autodataset_classes_status = {}
        self.autodataset_main_status = {}
        self.autodataset_tab.work_tab.text_logs.clear()
        self.autodataset_update_statuses()
        self.autodataset_update_progress(0)

    def set_btn_start_autodataset_state(self, started: bool=True):
        new_btn_start_style = self.autodataset_tab.work_tab.btn_start.styleSheet()
        if started:
            self.autodataset_tab.work_tab.btn_start.setText(tr("Стоп"))
            new_btn_start_style = new_btn_start_style.replace("#4CAF50", "#f44336")
            new_btn_start_style = new_btn_start_style.replace("#45a049", "#d32f2f")
            new_btn_start_style = new_btn_start_style.replace("#3d8b40", "#b71c1c")
        else:
            self.autodataset_tab.work_tab.btn_start.setText(tr("Запуск"))
            new_btn_start_style = new_btn_start_style.replace("#f44336", "#4CAF50")
            new_btn_start_style = new_btn_start_style.replace("#d32f2f", "#45a049")
            new_btn_start_style = new_btn_start_style.replace("#b71c1c", "#3d8b40")
        self.autodataset_tab.work_tab.btn_start.setStyleSheet(new_btn_start_style)

    def autodataset_embed_chrome(self, chrome_pid: int=0):
        # Встраивание окна поддерживается только в Windows (нужен win32 API): в macOS и
        # Linux Chrome работает отдельным окном, поэтому вкладка браузера не создаётся.
        if not chrome_pid or EmbeddedProgramWidget is None or not CAN_EMBED_PROGRAMS:
            return
        log.info("Embedding Chrome window (PID=%s)", chrome_pid)
        self.add_another_program_to_autodataset("chrome.exe", chrome_pid)


    def autodataset_set_chrome_lock(self, locked: bool=True):
        program_tab = getattr(self.autodataset_tab, "program_tab", None)
        if program_tab:
            program_tab.set_lock_resize(locked)


    def add_another_program_to_autodataset(self, program_name: str, program_pid: int=None):
        log.info("Embedding program into autodataset tab: %s (PID=%s)", program_name, program_pid)
        old_program_tab = getattr(self.autodataset_tab, "program_tab", None)
        if old_program_tab:
            self.autodataset_tab.tab_widget.removeTab(
                self.autodataset_tab.tab_widget.indexOf(old_program_tab))
            old_program_tab.deleteLater()
        self.autodataset_tab.program_tab = EmbeddedProgramWidget(program_name, program_pid)
        self.autodataset_tab.tab_widget.addTab(self.autodataset_tab.program_tab, program_name)
        def embed_on_tab_switch(index):
            current_widget = self.autodataset_tab.tab_widget.widget(index)
            if current_widget == self.autodataset_tab.program_tab:
                self.autodataset_tab.program_tab.embed_program()
        self.autodataset_tab.tab_widget.currentChanged.connect(embed_on_tab_switch)
        if self.autodataset_tab.tab_widget.currentWidget() == self.autodataset_tab.program_tab:
            self.autodataset_tab.program_tab.embed_program()
        self.autodataset_tab.program_tab.show()
        self.autodataset_tab.program_tab._showEvent()

    def autodataset_setup_interface(self):
        self.autodataset_tab.work_tab.horizontalLayout.setStretchFactor(self.autodataset_tab.work_tab.verticalLayout_left, 25)
        self.autodataset_tab.work_tab.horizontalLayout.setStretchFactor(self.autodataset_tab.work_tab.group_logs, 45)
        self.autodataset_tab.work_tab.horizontalLayout.setStretchFactor(self.autodataset_tab.work_tab.verticalLayout_right, 30)
        header_classes = self.autodataset_tab.work_tab.table_classes.horizontalHeader()
        header_classes.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_classes.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_classes.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_stages = self.autodataset_tab.work_tab.table_stages.horizontalHeader()
        header_stages.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_stages.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

    def autodataset_update_statuses(self):
        self.autodataset_visualise_classes_status()
        self.visualise_autodataset_main_status()
        self.autodataset_update_progress()

    def autodataset_set_object_status(
            self, object_name: str, status: int=None, object_class_name: str="No class", end_status: int=None):
        if object_name not in self.autodataset_classes_status:
            self.autodataset_classes_status[object_name] = {"class": object_class_name, "status": (0, 0)}
        self.autodataset_classes_status[object_name]["status"] = (
            status or self.autodataset_classes_status[object_name]["status"][0],
            end_status or self.autodataset_classes_status[object_name]["status"][1])
        self.autodataset_visualise_classes_status()

    def autodataset_visualise_classes_status(self):
        self.autodataset_tab.work_tab.table_classes.setRowCount(len(self.autodataset_classes_status))
        self.autodataset_tab.work_tab.table_classes.setHorizontalHeaderLabels([tr("Класс"), tr("Подкласс"), tr("Статус")])
        for r, (object_text, object) in enumerate(self.autodataset_classes_status.items()):
            self.autodataset_tab.work_tab.table_classes.setItem(r, 0, QTableWidgetItem(object["class"]))
            self.autodataset_tab.work_tab.table_classes.setItem(r, 1, QTableWidgetItem(object_text))
            self.autodataset_tab.work_tab.table_classes.setItem(r, 2, QTableWidgetItem(f"{object["status"][0]}/{object["status"][1]}"))

    def update_autodataset_main_status(self, name: str, progress: tuple | int=(0, 0)):
        self.autodataset_main_status[name] = progress if isinstance(progress, tuple) else (progress, self.autodataset_main_status.get(name)[1])
        self.autodataset_update_statuses()

    def visualise_autodataset_main_status(self):
        self.autodataset_tab.work_tab.table_stages.setRowCount(len(self.autodataset_main_status))
        self.autodataset_tab.work_tab.table_stages.setHorizontalHeaderLabels([tr("Этап"), tr("Статус")])
        for r, (stage, status) in enumerate(self.autodataset_main_status.items()):
            self.autodataset_tab.work_tab.table_stages.setItem(r, 0, QTableWidgetItem(stage))
            self.autodataset_tab.work_tab.table_stages.setItem(r, 1, QTableWidgetItem(f"{status[0]}/{status[1]}"))

    def autodataset_update_progress(self, progress: int=0):
        progress_status = sum(map(lambda x: x[1][0], self.autodataset_main_status.items()))
        full_progress_status = sum(map(lambda x: x[1][1], self.autodataset_main_status.items()))
        progress_proc = round(progress_status / full_progress_status * 100) if progress_status and full_progress_status else 0
        progress_proc = progress_proc if progress_proc < 100 else 100
        self.autodataset_tab.work_tab.progress_bar.setValue(progress_proc if not progress else progress)

    def autodataset_log(self, text: str, otstup: int=0):
        self.autodataset_tab.work_tab.text_logs.append('\n'*otstup+f'[{datetime.now().strftime("%H:%M:%S")}] {text}')

    def autodataset_set_image(self, image_path: str | np.ndarray, np_rgb_image: bool=None):
        if np_rgb_image is not None and np_rgb_image.size>0:
            qimage = QImage(
                np_rgb_image.data, np_rgb_image.shape[1], 
                np_rgb_image.shape[0], np_rgb_image.shape[1]*3,
                QImage.Format.Format_RGB888)
        else:
            qimage = QImage(image_path)
        pixmap = QPixmap.fromImage(qimage)
        self.autodataset_tab.work_tab.label_image.setPixmap(
            pixmap.scaled(
                self.autodataset_tab.work_tab.label_image.width(),
                self.autodataset_tab.work_tab.label_image.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
        ))
        self.autodataset_tab.work_tab.label_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.autodataset_tab.work_tab.label_image_path.setText(image_path)


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.project_resize_timer.start(100)
        self.dataset_resize_timer.start(100)