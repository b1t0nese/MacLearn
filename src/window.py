from PyQt6 import uic
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHeaderView,
                             QTableWidgetItem, QFileDialog, QLabel)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QTimer, Qt
from datetime import datetime
import os

uis_path = os.path.join(os.path.dirname(__file__), "uis")



class MainWindowUI(QMainWindow):
    def __init__(self):
        super().__init__()

    def initUI(self):
        uic.loadUi(os.path.join(uis_path, "mainwindow.ui"), self)

        self.project_tab = uic.loadUi(os.path.join(uis_path, "tabs", "project_tab.ui"))
        self.tabWidget.addTab(self.project_tab, "Проект")
        self.project_tab.btn_add_class.clicked.connect(self.add_class)
        self.project_tab.class_objects = []

        self.autodataset_tab = uic.loadUi(os.path.join(uis_path, "tabs", "autodataset_tab.ui"))
        self.tabWidget.addTab(self.autodataset_tab, "Автодатасет")
        self.setup_autodataset_interface()
        self.autodataset_classes_status = {}
        self.autodataset_main_status = {}

        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.update_all_class_layouts)


    def update_autodataset_statuses(self):
        self.update_autodataset_classes_status()
        self.visualise_autodataset_classes_status()

    def setup_autodataset_interface(self):
        self.autodataset_tab.horizontalLayout.setStretchFactor(self.autodataset_tab.verticalLayout_left, 25)
        self.autodataset_tab.horizontalLayout.setStretchFactor(self.autodataset_tab.group_logs, 45)
        self.autodataset_tab.horizontalLayout.setStretchFactor(self.autodataset_tab.verticalLayout_right, 30)
        header_classes = self.autodataset_tab.table_classes.horizontalHeader()
        header_classes.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_classes.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_classes.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_stages = self.autodataset_tab.table_stages.horizontalHeader()
        header_stages.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_stages.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

    def update_autodataset_classes_status(self):
        local_classes_status = {}    
        for class_obj in self.project_tab.class_objects:
            if class_obj.class_checkbox.isChecked():
                for subclass in class_obj.subclass_widgets:
                    subclass_text = subclass.object_name.text()
                    subclass_data = {
                        "example_image": subclass.object_image.my_image_path,
                        "class": class_obj.class_name.text(),
                        "status": f"{self.autodataset_classes_status[subclass_text]["status"].split("/")[0]\
                                     if subclass_text in self.autodataset_classes_status else 0}"+\
                                        f"/{self.project_tab.spin_images_per_class.value()//len(class_obj.subclass_widgets)}"
                    }
                    local_classes_status[subclass_text] = subclass_data
        self.autodataset_classes_status = local_classes_status.copy()

    def update_autodataset_subclass_status(self, subclass_name: str, status: int):
        self.autodataset_classes_status[subclass_name]["status"] = f"{status}/{self.autodataset_classes_status[subclass_name]["status"].split("/")[1]}"
        self.visualise_autodataset_classes_status()

    def visualise_autodataset_classes_status(self):
        self.autodataset_tab.table_classes.setRowCount(len(self.autodataset_classes_status))
        self.autodataset_tab.table_classes.setHorizontalHeaderLabels(["Класс", "Подкласс", "Статус"])
        for r, subclass_data in enumerate(self.autodataset_classes_status.items()):
            subclass_text, subclass = subclass_data
            self.autodataset_tab.table_classes.setItem(r, 0, QTableWidgetItem(subclass["class"]))
            self.autodataset_tab.table_classes.setItem(r, 1, QTableWidgetItem(subclass_text))
            self.autodataset_tab.table_classes.setItem(r, 2, QTableWidgetItem(subclass["status"]))

    def autodataset_log(self, text: str, otstup: int=0):
        self.autodataset_tab.text_logs.append('\n'*otstup+f'[{datetime.now().strftime("%H:%M:%S")}] {text}')

    def autodataset_set_image(self, image_path: str):
        pixmap = QPixmap.fromImage(QImage(image_path))
        self.autodataset_tab.label_image.setPixmap(
            pixmap.scaled(
                self.autodataset_tab.label_image.width(),
                self.autodataset_tab.label_image.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        self.autodataset_tab.label_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.autodataset_tab.label_image_path.setText(image_path)

    ... # другие функции специально для "Автодатасет" табы


    def set_obj_card_image(self, image_label: QLabel, image_path: str) -> bool:
        try:
            pixmap = QPixmap.fromImage(QImage(image_path))
            image_label.setPixmap(
                pixmap.scaled(
                    image_label.parent().width(), image_label.parent().height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.my_image_path = image_path
            return True
        except Exception as e:
            image_label.setText(f"Ошибка: {e}")
            return False

    def add_class(self, class_name: str = None, enabled: bool = True) -> QWidget:
        class_widget = uic.loadUi(os.path.join(uis_path, "widgets", "class_field.ui"))
        self.project_tab.classes_vertical_layout.addWidget(class_widget)
        self.project_tab.class_objects.append(class_widget)
        class_widget.subclass_widgets = []
        class_widget.grid_layout = class_widget.class_grid_layout
        class_widget.class_checkbox.stateChanged.connect(self.show_class)
        class_widget.class_delete.clicked.connect(
            lambda: self.delete_class(class_widget))
        class_widget.class_add_subclass.clicked.connect(
            lambda: self.add_subclass(class_widget))
        if class_name:
            class_widget.class_name.setText(class_name)
        class_widget.class_checkbox.setChecked(enabled)
        self.resize_timer.start(100)
        return class_widget

    def show_class(self):
        checkbox = self.sender()
        class_widget, enabled = checkbox.parent(), checkbox.isChecked()
        class_widget.class_name.setEnabled(enabled)
        class_widget.class_add_subclass.setEnabled(enabled)
        for subclass in class_widget.subclass_widgets:
            subclass.setEnabled(enabled)

    def delete_class(self, class_widget):
        for subclass in class_widget.subclass_widgets:
            subclass.deleteLater()
        class_widget.subclass_widgets.clear()
        class_widget.setParent(None)
        class_widget.deleteLater()
        self.project_tab.class_objects.remove(class_widget)

    def add_subclass(self, parent_class, search_text: str = None,
                     subclass_image: str = None) -> QWidget:
        object_card = uic.loadUi(os.path.join(uis_path, "widgets", "object_card.ui"))
        object_card.object_delete.clicked.connect(
            lambda: self.delete_subclass(object_card, parent_class))
        parent_class.subclass_widgets.append(object_card)
        object_card.object_image.my_image_path = ""
        if subclass_image:
            self.set_obj_card_image(object_card.object_image, subclass_image)
        object_card.object_image.mousePressEvent = lambda event:\
            self.subclass_image_click(object_card.object_image, event)
        if search_text:
            object_card.object_name.setText(search_text)
        self.update_class_layout(parent_class)
        return object_card

    def subclass_image_click(self, label, event):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Images (*.png *.jpg)")
        path, ok = file_dialog.getOpenFileName()
        if ok:
            self.set_obj_card_image(label, path)

    def delete_subclass(self, subclass_widget, parent_class=None):
        if parent_class is None and hasattr(subclass_widget, 'parent_class'):
            parent_class = subclass_widget.parent_class
        if parent_class and subclass_widget in parent_class.subclass_widgets:
            parent_class.subclass_widgets.remove(subclass_widget)
            subclass_widget.setParent(None)
            subclass_widget.deleteLater()
            self.update_class_layout(parent_class)
        else:
            subclass_widget.setParent(None)
            subclass_widget.deleteLater()

    def update_class_layout(self, class_widget):
        if not class_widget.subclass_widgets:
            return

        container_width = class_widget.width()
        subclass_width = 270
        spacing = 10
        if container_width<=0:
            return
        max_subclasses_per_row = max(1, (container_width - spacing)//(subclass_width+spacing))

        for i in reversed(range(class_widget.grid_layout.count())):
            item = class_widget.grid_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        add_button = class_widget.class_add_subclass
        total_widgets = len(class_widget.subclass_widgets)+1

        for i, widget in enumerate(class_widget.subclass_widgets):
            row = i // max_subclasses_per_row
            col = i % max_subclasses_per_row
            class_widget.grid_layout.addWidget(widget, row, col)

        last_row = (total_widgets-1)//max_subclasses_per_row
        last_col = (total_widgets-1)%max_subclasses_per_row
        class_widget.grid_layout.addWidget(add_button, last_row, last_col)

    def update_all_class_layouts(self):
        for i in range(self.project_tab.classes_vertical_layout.count()):
            item = self.project_tab.classes_vertical_layout.itemAt(i)
            if item and hasattr(item.widget(), 'subclass_widgets'):
                self.update_class_layout(item.widget())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start(100)