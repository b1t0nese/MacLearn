from PyQt6 import uic
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHeaderView, QTabWidget,
                             QTableWidgetItem, QFileDialog, QVBoxLayout, QMessageBox)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QTimer, Qt
from datetime import datetime
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
    
    def initUI(self, object_name: str=None, object_image: str=None, click_image: callable=None):
        uic.loadUi(os.path.join(uis_path, "widgets", "object_card.ui"), self)
        self.object_image.my_image_path = ""
        if object_image:
            self.update_object_image(object_image)
        self.object_image.mousePressEvent = self.object_image_click if not click_image else click_image
        if object_name:
            self.object_name.setText(object_name)
        self.object_delete.clicked.connect(
            lambda: self.delete_object())


    def delete_object(self):
        self.setParent(None)
        self.deleteLater()


    def set_object_image_pixmap(self, image_path):
        self.object_image_pixmap = QPixmap.fromImage(QImage(image_path)).scaled(
            self.object_image.parent().maximumWidth(),
            self.object_image.parent().maximumHeight(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.object_image.my_image_path = image_path


    def update_object_image(self, image_path: str=None) -> bool:
        try:
            if image_path:
                self.set_object_image_pixmap(image_path)
            elif not hasattr(self, "object_image_pixmap") and not self.object_image_pixmap:
                return False
            self.object_image.setPixmap(self.object_image_pixmap)
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
        self.objects_widgets = []

    def initUI(self, class_name: str=None, enabled: bool=True):
        uic.loadUi(os.path.join(uis_path, "widgets", "class_field.ui"), self)
        self.class_checkbox.stateChanged.connect(self.show_class)
        self.class_delete.clicked.connect(self.delete_class)
        self.class_add_object.clicked.connect(lambda: (self.add_object(), self.update_layout()))
        self.class_checkbox.setChecked(enabled)
        if class_name:
            self.class_name.setText(class_name)
        self.show_class()


    def show_class(self, enabled: bool=None):
        if enabled is None:
            enabled = self.class_checkbox.isChecked()
        else:
            self.class_checkbox.setChecked(enabled)
        self.class_name.setEnabled(enabled)
        self.class_add_object.setEnabled(enabled)
        for object in self.objects_widgets:
            object.setEnabled(enabled)


    def delete_class(self):
        for object in self.objects_widgets:
            self.delete_object(object)
        self.objects_widgets.clear()
        self.setParent(None)
        self.deleteLater()


    def add_object(self, object_name: str = None, object_image: str = None,
                   click_image: callable=None) -> ObjectCardWidget:
        object_card = ObjectCardWidget()
        object_card.initUI(object_name=object_name, object_image=object_image, click_image=click_image)
        object_card.object_delete.clicked.connect(
            lambda: (self.delete_object(object_card), self.update_layout()))
        self.objects_widgets.append(object_card)
        return object_card


    def delete_object(self, object_widget: ObjectCardWidget):
        if object_widget in self.objects_widgets:
            self.objects_widgets.remove(object_widget)
            object_widget.delete_object()


    def get_object(self, object_name: str = None) -> bool | ObjectCardWidget:
        for object in self.objects_widgets:
            if object.object_name.text()==object_name:
                return object
        return False


    def update_layout(self):
        if self.width() <= 0 or not self.objects_widgets:
            return

        all_widgets = self.objects_widgets + [self.class_add_object]
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
        self.project_tab.btn_add_class.clicked.connect(self.project_add_class)
        self.project_tab.class_objects = []
        self.project_resize_timer = QTimer()
        self.project_resize_timer.setSingleShot(True)
        self.project_resize_timer.timeout.connect(self.project_update_all_class_layouts)

    def project_add_class(self, class_name: str = None, enabled: bool = True) -> ClassFieldWidget:
        class_widget = ClassFieldWidget()
        class_widget.initUI(class_name, enabled)
        self.project_tab.classes_vertical_layout.addWidget(class_widget)
        self.project_tab.class_objects.append(class_widget)
        class_widget.class_delete.clicked.connect(
            lambda: self.project_delete_class(class_widget))
        return class_widget

    def project_delete_class(self, class_widget: ClassFieldWidget):
        class_widget.delete_class()
        self.project_tab.class_objects.remove(class_widget)

    def project_update_all_class_layouts(self):
        for i in range(self.project_tab.classes_vertical_layout.count()):
            item = self.project_tab.classes_vertical_layout.itemAt(i)
            if item and hasattr(item.widget(), 'objects_widgets'):
                item.widget().update_layout()


    def dataset_initUI(self):
        self.dataset_tab = uic.loadUi(os.path.join(uis_path, "tabs", "dataset_tab.ui"))
        self.tabWidget.addTab(self.dataset_tab, "Датасет")
        self.dataset_tab.classes_tabs = {}
        self.dataset_resize_timer = QTimer()
        self.dataset_resize_timer.setSingleShot(True)
        self.dataset_resize_timer.timeout.connect(self.dataset_update_all_class_layouts)
        self.dataset_tab.tab_bar.currentChanged.connect(self.dataset_on_tab_changed)

    def dataset_on_tab_changed(self, index):
        if index >= 0:
            class_name = self.dataset_tab.tab_bar.tabText(index)
            if class_name in self.dataset_tab.classes_tabs:
                for widget in self.dataset_tab.classes_tabs.values():
                    widget.hide()
                selected_widget = self.dataset_tab.classes_tabs[class_name]
                selected_widget.show()
                layout = self.dataset_tab.content_widget.layout()
                if selected_widget.parent() != self.dataset_tab.content_widget:
                    layout.addWidget(selected_widget)
                for field_widget in selected_widget.fields_list:
                    field_widget.update_layout()

    def dataset_add_class(self, class_name: str = None) -> QWidget:
        overview_widget = uic.loadUi(os.path.join(uis_path, "widgets", "overview_class.ui"))
        overview_widget.overview_group.setTitle(class_name)
        self.dataset_tab.classes_tabs[class_name] = overview_widget
        self.dataset_tab.classes_tabs[class_name].fields_list = []
        if self.dataset_tab.tab_bar.count() == 0:
            self.dataset_tab.content_widget.layout().addWidget(overview_widget)
            overview_widget.show()
        else:
            overview_widget.hide()
        self.dataset_tab.tab_bar.addTab(class_name)
        return overview_widget

    def dataset_add_class_field_by_type(self, class_name: str, type_name: str, enabled: bool = True) -> ClassFieldWidget:
        field_widget = ClassFieldWidget()
        field_widget.initUI(type_name, enabled)
        field_widget.class_delete.clicked.disconnect()
        field_widget.class_delete.clicked.connect(
            lambda: self.dataset_delete_class_field_widget(field_widget))
        self.dataset_tab.classes_tabs[class_name].overview_vertical_layout.addWidget(field_widget)
        self.dataset_tab.classes_tabs[class_name].fields_list.append(field_widget)
        return field_widget

    def dataset_delete_class_overview(self, overview_class_widget: QWidget, user_call: bool=True) -> bool:
        if user_call:
            reply = QMessageBox.question(
                self, "Удаление класса",
                "Вы точно хотите удалить класс? Все изображения которые относились к нему также будут удалены.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if (not user_call) or reply == QMessageBox.StandardButton.Yes:
            class_name_to_remove = self.get_overview_class_name_in_dataset(overview_class_widget)
            if class_name_to_remove:
                for i in range(self.dataset_tab.tab_bar.count()):
                    if self.dataset_tab.tab_bar.tabText(i) == class_name_to_remove:
                        self.dataset_tab.tab_bar.removeTab(i)
                        break
                self.dataset_tab.content_widget.layout().removeWidget(overview_class_widget)
                overview_class_widget.deleteLater()
                del self.dataset_tab.classes_tabs[class_name_to_remove]
                return True
        return False

    def dataset_delete_class_field_widget(self, field_widget: QWidget, user_call: bool=True) -> bool:
        if user_call:
            reply = QMessageBox.question(
                self, "Удаление данных класса", "Вы точно хотите удалить эти изображения?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if (not user_call) or reply == QMessageBox.StandardButton.Yes:
            field_widget.delete_class()
            class_widget = None
            for widget in self.dataset_tab.classes_tabs.values():
                if field_widget in widget.fields_list:
                    class_widget = widget
                    break
            if class_widget:
                class_widget.fields_list.remove(field_widget)
                if class_widget.overview_vertical_layout:
                    class_widget.overview_vertical_layout.removeWidget(field_widget)
                field_widget.deleteLater()
            return True
        else:
            return False

    def get_class_field_in_dataset(self, class_name: str, field_name: str) -> bool | QWidget:
        class_tab = self.dataset_tab.classes_tabs.get(class_name)
        if class_tab:
            for field_widget in class_tab.fields_list:
                if field_widget.class_name.text()==field_name:
                    return field_widget
        return False

    def get_overview_class_name_in_dataset(self, overview_class_widget: QWidget) -> bool | str:
        class_name = False
        for cur_class_name, widget in self.dataset_tab.classes_tabs.items():
            if widget == overview_class_widget:
                class_name = cur_class_name
                break
        return class_name

    def dataset_update_all_class_layouts(self):
        for class_name, class_overview in self.dataset_tab.classes_tabs.items():
            for field_widget in class_overview.fields_list:
                field_widget.update_layout()


    def autodataset_initUI(self):
        self.autodataset_tab = QWidget()
        self.autodataset_tab.tab_widget = QTabWidget()
        self.autodataset_tab.work_tab = uic.loadUi(os.path.join(uis_path, "tabs", "autodataset_tab.ui"))
        self.autodataset_tab.setLayout(QVBoxLayout())
        self.autodataset_tab.tab_widget.addTab(self.autodataset_tab.work_tab, "Работа")
        self.autodataset_tab.layout().addWidget(self.autodataset_tab.tab_widget)
        self.tabWidget.addTab(self.autodataset_tab, "Автодатасет")
        self.setup_autodataset_interface()
        self.setup_autodataset()

    def setup_autodataset(self):
        self.autodataset_classes_status = {}
        self.autodataset_main_status = {}
        self.autodataset_tab.work_tab.text_logs.clear()
        self.update_autodataset_statuses()
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

    def setup_autodataset_interface(self):
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

    def update_autodataset_statuses(self):
        self.update_autodataset_classes_status()
        self.visualise_autodataset_classes_status()
        self.visualise_autodataset_main_status()
        self.autodataset_update_progress()

    def update_autodataset_classes_status(self):
        local_classes_status = {}    
        for class_obj in self.project_tab.class_objects:
            if class_obj.class_checkbox.isChecked():
                for object in class_obj.objects_widgets:
                    object_text = object.object_name.text()
                    images_per_subclass = self.project_tab.spin_images_per_class.value()//len(class_obj.objects_widgets)
                    images_per_subclass += images_per_subclass//5 if self.project_tab.cb_validation_data.isChecked() else 0
                    object_data = {
                        "example_image": object.object_image.my_image_path,
                        "class": class_obj.class_name.text(),
                        "status": (self.autodataset_classes_status[object_text]["status"][0]\
                                   if object_text in self.autodataset_classes_status else 0, images_per_subclass)
                    }
                    local_classes_status[object_text] = object_data
        self.autodataset_classes_status = local_classes_status.copy()

    def update_autodataset_object_status(self, object_name: str, status: int):
        self.autodataset_classes_status[object_name]["status"] = (status, self.autodataset_classes_status[object_name]["status"][1])
        self.visualise_autodataset_classes_status()

    def visualise_autodataset_classes_status(self):
        self.autodataset_tab.work_tab.table_classes.setRowCount(len(self.autodataset_classes_status))
        self.autodataset_tab.work_tab.table_classes.setHorizontalHeaderLabels(["Класс", "Подкласс", "Статус"])
        for r, (object_text, object) in enumerate(self.autodataset_classes_status.items()):
            self.autodataset_tab.work_tab.table_classes.setItem(r, 0, QTableWidgetItem(object["class"]))
            self.autodataset_tab.work_tab.table_classes.setItem(r, 1, QTableWidgetItem(object_text))
            self.autodataset_tab.work_tab.table_classes.setItem(r, 2, QTableWidgetItem(f"{object["status"][0]}/{object["status"][1]}"))

    def update_autodataset_main_status(self, name: str, progress: tuple | int=(0, 0)):
        self.autodataset_main_status[name] = progress if isinstance(progress, tuple) else (progress, self.autodataset_main_status.get(name)[1])
        self.update_autodataset_statuses()

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

    def autodataset_set_image(self, image_path: str, np_rgb_image=None):
        if np_rgb_image is not None and np_rgb_image.size > 0:
            qimage = QImage(
                np_rgb_image.data, 
                np_rgb_image.shape[1], 
                np_rgb_image.shape[0], 
                np_rgb_image.shape[1] * 3, 
                QImage.Format.Format_RGB888
            )
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