from PyQt6 import uic
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHeaderView, QTabWidget,
                             QTableWidgetItem, QFileDialog, QVBoxLayout, QMessageBox)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QTimer, Qt
from datetime import datetime
from typing import Callable
import numpy as np
import sys
import os

from .embedded_program_qt import EmbeddedProgramWidget


if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)
uis_path = os.path.join(base_path, "uis")



class ObjectCardWidget(QWidget):
    def __init__(self):
        super().__init__()

    def initUI(self, object_name: str=None, object_image: str | np.ndarray=None,
               name_enabled: bool=True, click_image: Callable=None):
        uic.loadUi(os.path.join(uis_path, "widgets", "object_card.ui"), self)
        self.object_image.my_image_path = ""
        if object_image is not None:
            self.update_object_image(object_image)
        self.object_image.mousePressEvent = self.object_image_click if not click_image else click_image
        if object_name:
            self.object_name.setText(object_name)
        self.object_name.setEnabled(name_enabled)
        self.object_delete.clicked.connect(
            lambda: self.delete_object())

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
    def __init__(self):
        super().__init__()
        self.objects: list[ObjectCardWidget] = []

    def initUI(self, class_name: str=None, enabled: bool=True,
               import_and_export_buttons: bool=True, name_enabled: bool=True):
        uic.loadUi(os.path.join(uis_path, "widgets", "class_field.ui"), self)
        if not import_and_export_buttons:
            self.class_export_files.deleteLater()
            self.class_import_files.deleteLater()
        self.class_checkbox.stateChanged.connect(self.show_class)
        self.class_delete.clicked.connect(self.delete_class)
        self.class_add_object.clicked.connect(lambda: (self.add_object(), self.update_layout()))
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
        object_card.object_delete.clicked.connect(
            lambda: (self.delete_object(object_card), self.update_layout()))
        self.objects.append(object_card)
        return object_card

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
        uic.loadUi(os.path.join(uis_path, "widgets", "overview_class.ui"), self)
        if class_name:
            self.overview_group.setTitle(class_name)
        self.tab_bar.currentChanged.connect(self.scroll_to_field)
        self.lineEdit_search.textChanged.connect(self.search_update)
        self.overview_scroll_area.verticalScrollBar().valueChanged.connect(self.update_tab_selection_from_scroll)


    def add_field(self, field_widget: ClassFieldWidget, field_name: str):
        self.overview_vertical_layout.addWidget(field_widget)
        self.fields.append(field_widget)
        self.tab_bar.addTab(field_name)

    def remove_field(self, field_widget: ClassFieldWidget):
        if field_widget in self.fields:
            for i in range(self.tab_bar.count()):
                if self.tab_bar.tabText(i)==field_widget.class_name.text():
                    self.tab_bar.removeTab(i)
                    break
            self.fields.remove(field_widget)
            if self.overview_vertical_layout:
                self.overview_vertical_layout.removeWidget(field_widget)
            field_widget.delete_class()


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
        uic.loadUi(os.path.join(uis_path, "mainwindow.ui"), self)
        self.project_initUI()
        self.dataset_initUI()
        self.autodataset_initUI()


    def project_initUI(self):
        self.project_tab = uic.loadUi(os.path.join(uis_path, "tabs", "project_tab.ui"))
        self.tabWidget.addTab(self.project_tab, "Проект")
        self.project_tab.project_overview = OverviewClassWidget()
        self.project_tab.project_overview.initUI("Классы объектов")
        self.project_tab.verticalLayout_2.insertWidget(0, self.project_tab.project_overview)
        self.project_tab.btn_add_class.clicked.connect(self.project_add_class)
        self.project_resize_timer = QTimer()
        self.project_resize_timer.setSingleShot(True)
        self.project_resize_timer.timeout.connect(self.project_tab.project_overview.update_all_fields_layouts)

    def project_add_class(self, class_name: str = None, enabled: bool = True) -> ClassFieldWidget:
        class_name = class_name or f"Класс {len(self.project_tab.project_overview.fields) + 1}"
        class_widget = ClassFieldWidget()
        class_widget.initUI(class_name, enabled, False)
        self.project_tab.project_overview.add_field(class_widget, class_name)
        class_widget.class_delete.clicked.connect(
            lambda: self.project_tab.project_overview.remove_field(class_widget))
        return class_widget


    def dataset_initUI(self):
        self.dataset_tab = uic.loadUi(os.path.join(uis_path, "tabs", "dataset_tab.ui"))
        self.tabWidget.addTab(self.dataset_tab, "Датасет")
        self.dataset_tab.classes_tabs = {}
        self.dataset_resize_timer = QTimer()
        self.dataset_resize_timer.setSingleShot(True)
        self.dataset_resize_timer.timeout.connect(self.dataset_update_all_class_layouts)
        self.dataset_tab.tab_bar.currentChanged.connect(self.dataset_on_tab_changed)

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
        return overview_widget

    def dataset_delete_class(self, overview_widget: OverviewClassWidget, user_call: bool=True) -> bool:
        if user_call:
            reply = QMessageBox.question(
                self, "Удаление класса",
                "Вы точно хотите удалить класс? Все изображения которые относились к нему также будут удалены.",
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
        field_widget.initUI(field_name, enabled, True, False)
        field_widget.class_delete.clicked.disconnect()
        field_widget.class_delete.clicked.connect(
            lambda: self.dataset_delete_class_field_widget(field_widget))
        self.dataset_tab.classes_tabs[class_name].add_field(field_widget, field_name)
        return field_widget

    def dataset_delete_class_field_widget(self, field_widget: ClassFieldWidget, user_call: bool=True) -> bool:
        if user_call:
            reply = QMessageBox.question(
                self, "Удаление данных класса", "Вы точно хотите удалить эти изображения?",
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
        self.autodataset_tab.work_tab = uic.loadUi(os.path.join(uis_path, "tabs", "autodataset_tab.ui"))
        self.autodataset_tab.setLayout(QVBoxLayout())
        self.autodataset_tab.tab_widget.addTab(self.autodataset_tab.work_tab, "Работа")
        self.autodataset_tab.layout().addWidget(self.autodataset_tab.tab_widget)
        self.tabWidget.addTab(self.autodataset_tab, "Автодатасет")
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
            self.autodataset_tab.work_tab.btn_start.setText("Стоп")
            new_btn_start_style = new_btn_start_style.replace("#4CAF50", "#f44336")
            new_btn_start_style = new_btn_start_style.replace("#45a049", "#d32f2f")
            new_btn_start_style = new_btn_start_style.replace("#3d8b40", "#b71c1c")
        else:
            self.autodataset_tab.work_tab.btn_start.setText("Запуск")
            new_btn_start_style = new_btn_start_style.replace("#f44336", "#4CAF50")
            new_btn_start_style = new_btn_start_style.replace("#d32f2f", "#45a049")
            new_btn_start_style = new_btn_start_style.replace("#b71c1c", "#3d8b40")
        self.autodataset_tab.work_tab.btn_start.setStyleSheet(new_btn_start_style)

    def add_another_program_to_autodataset(self, program_name: str):
        self.autodataset_tab.program_tab = EmbeddedProgramWidget(program_name)
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
        self.autodataset_tab.work_tab.table_classes.setHorizontalHeaderLabels(["Класс", "Подкласс", "Статус"])
        for r, (object_text, object) in enumerate(self.autodataset_classes_status.items()):
            self.autodataset_tab.work_tab.table_classes.setItem(r, 0, QTableWidgetItem(object["class"]))
            self.autodataset_tab.work_tab.table_classes.setItem(r, 1, QTableWidgetItem(object_text))
            self.autodataset_tab.work_tab.table_classes.setItem(r, 2, QTableWidgetItem(f"{object["status"][0]}/{object["status"][1]}"))

    def update_autodataset_main_status(self, name: str, progress: tuple | int=(0, 0)):
        self.autodataset_main_status[name] = progress if isinstance(progress, tuple) else (progress, self.autodataset_main_status.get(name)[1])
        self.autodataset_update_statuses()

    def visualise_autodataset_main_status(self):
        self.autodataset_tab.work_tab.table_stages.setRowCount(len(self.autodataset_main_status))
        self.autodataset_tab.work_tab.table_stages.setHorizontalHeaderLabels(["Этап", "Статус"])
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