from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QTimer
import os

uis_path = os.path.join(os.path.dirname(__file__), "uis")



class MainWindowUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        uic.loadUi(os.path.join(uis_path, "mainwindow.ui"), self)

        self.project_tab = uic.loadUi(os.path.join(uis_path, "tabs", "project_tab.ui"))
        self.tabWidget.addTab(self.project_tab, "Проект")

        self.project_tab.btn_add_class.clicked.connect(self.add_class)

        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.update_all_class_layouts)


    # ==== РАБОТА С КЛАССАМИ В ТАБЕ "Проект" ====

    def add_class(self):
        class_widget = uic.loadUi(os.path.join(uis_path, "widgets", "class_field.ui"))
        self.project_tab.classes_vertical_layout.addWidget(class_widget)
        class_widget.subclass_widgets = []
        class_widget.grid_layout = class_widget.class_grid_layout
        class_widget.class_checkbox.stateChanged.connect(self.show_class)
        class_widget.class_delete.clicked.connect(
            lambda: self.delete_class(class_widget))
        class_widget.class_add_subclass.clicked.connect(
            lambda: self.add_subclass(class_widget))
        self.resize_timer.start(100)

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

    def add_subclass(self, parent_class):
        object_card = uic.loadUi(os.path.join(uis_path, "widgets", "object_card.ui"))
        object_card.object_delete.clicked.connect(
            lambda: self.delete_subclass(object_card, parent_class))
        parent_class.subclass_widgets.append(object_card)
        self.update_class_layout(parent_class)

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