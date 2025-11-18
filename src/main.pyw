from window import MainWindowUI
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PyQt6.QtCore import QThread
import sys

from project_manager import Project
from autodataset import AutoDataset


class App:
    def __init__(self):
        self.autodataset_worker = None
        self.autodataset_worker_thread = None
        self.open_project()

    def start(self, app):
        self.appApplication = app
        sys.exit(self.appApplication.exec())

    def close_application(self, event=None):
        if (hasattr(self, "appApplication") and hasattr(self, "windowUI")
            and self.appApplication and self.windowUI):
            if self.autodataset_worker:
                self.autodataset_worker.driver.quit()
            self.windowUI.close()
            self.appApplication.quit()
        if event:
            if hasattr(self.windowUI, "original_close_event"):
                self.windowUI.original_close_event(event)
            else:
                event.accept()

    def config_window(self):
        self.windowUI.setWindowTitle(f'{self.windowUI.windowTitle()} ("{self.project_data.project_path}")')
        self.windowUI.project_tab.btn_save_project.clicked.connect(self.save_project)
        self.windowUI.autodataset_tab.btn_start.clicked.connect(self.toggle_autodataset_work)
        self.windowUI.actionOpen.triggered.connect(self.open_project)
        self.windowUI.actionSave.triggered.connect(self.save_project)
        self.windowUI.actionSave_As.triggered.connect(self.save_project_as)
        self.windowUI.actionExit.triggered.connect(self.close_application)
        self.windowUI.original_close_event = self.windowUI.closeEvent
        self.windowUI.closeEvent = self.close_application.__get__(self, type(self.windowUI))

    def init_project_conf_in_window(self):
        project_conf = self.project_data.get_project_conf()
        for clas in project_conf["classes"]:
            cur_class_widget = self.windowUI.add_class(clas["class_name"], clas["enabled"])
            for subclas in clas["subclasses"]:
                img_fullpath = (
                    self.project_data.get_full_path("example_images", subclas["example_image"])
                    if subclas["example_image"] else None)
                self.windowUI.add_subclass(cur_class_widget, subclas["search_query"], img_fullpath)
        pr_tab = self.windowUI.project_tab
        pr_tab.cb_validation_data.setChecked(project_conf["configuration"]["validation_data"])
        pr_tab.cb_augmented_images.setChecked(project_conf["configuration"]["augmented_images"])
        pr_tab.cb_annotation.setChecked(project_conf["configuration"]["annotation"])
        pr_tab.combo_annotation_format.setCurrentText(project_conf["configuration"]["annotation_format"])
        pr_tab.spin_images_per_class.setValue(project_conf["configuration"]["images_per_class"])
        pr_tab.combo_images_size.setCurrentText(project_conf["configuration"]["images_size"])

    def open_project(self, project_path: str = None) -> bool:
        if not project_path:
            project_path = QFileDialog.getExistingDirectory(None, "Выберите папку проекта", "")

        if project_path:
            if hasattr(self, "windowUI") and self.windowUI:
                self.windowUI.close()
                self.windowUI.deleteLater()
            if hasattr(self, "autodataset_worker") and self.autodataset_worker:
                self.autodataset_worker.driver.quit()
                self.autodataset_worker = None
            self.windowUI = MainWindowUI()
            if not Project.path_is_project(project_path):
                reply = QMessageBox.question(
                    self.windowUI, "Проект не найден или повреждён",
                    f'Проект по заданному пути "{project_path}" не найден, или повреждён. '
                    + "Будут созданы недостающие папки и файлы.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Close:
                    self.close_application()
                elif reply == QMessageBox.StandardButton.No:
                    self.open_project()
                    return

            self.project_data = Project(project_path)
            self.autodataset_worker = AutoDataset(self.project_data)
            self.windowUI.initUI()
            self.config_window()
            self.init_project_conf_in_window()
            self.windowUI.update_autodataset_statuses()
            self.windowUI.show()

        else:
            sys.exit()

    def save_project(self):
        pr_tab = self.windowUI.project_tab
        local_project_conf = {
            "configuration": {
                "validation_data": pr_tab.cb_validation_data.isChecked(),
                "augmented_images": pr_tab.cb_augmented_images.isChecked(),
                "annotation": pr_tab.cb_annotation.isChecked(),
                "annotation_format": pr_tab.combo_annotation_format.currentText(),
                "images_per_class": pr_tab.spin_images_per_class.value(),
                "images_size": pr_tab.combo_images_size.currentText(),
            },
            "classes_conf": [],
        }
        for i, class_obj in enumerate(self.windowUI.project_tab.class_objects):
            local_class = {
                "class_name": class_obj.class_name.text(),
                "enabled": class_obj.class_checkbox.isChecked(),
                "subclasses": [],
            }
            for subclass in class_obj.subclass_widgets:
                local_class["subclasses"].append(
                    {
                        "search_query": subclass.object_name.text(),
                        "example_image": subclass.object_image.my_image_path,
                    }
                )
            local_project_conf["classes_conf"].append(local_class)
        self.project_data.save(**local_project_conf)
        self.windowUI.update_autodataset_statuses()

    def save_project_as(self):
        new_project_path = QFileDialog.getExistingDirectory(self.windowUI, "Выберите папку для сохранения")
        if new_project_path:
            status, message = self.project_data.save_as(new_project_path)
            if status:
                QMessageBox.information(self.windowUI, "Успех", message)
                reply = QMessageBox.question(
                    self.windowUI, "Перезапуск в новой директории",
                    f'Перезапустить окно в новой директории "{new_project_path}"?.',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.open_project(new_project_path)
            else:
                QMessageBox.warning(self.windowUI, "Ошибка", message)

    def toggle_autodataset_work(self):
        if self.autodataset_worker_thread:
            self.stop_autodataset()
        else:
            self.start_autodataset()

    def start_autodataset(self):
        self.autodataset_thread = QThread()
        self.autodataset_worker.moveToThread(self.autodataset_thread)

        self.autodataset_thread.started.connect(self.autodataset_worker.run)
        self.autodataset_worker.finished.connect(self.stop_autodataset)

        self.autodataset_worker.log_field.connect(self.windowUI.autodataset_log)
        self.autodataset_worker.cur_image_label.connect(self.windowUI.autodataset_set_image)
        self.autodataset_worker.subclass_updated.connect(self.windowUI.update_autodataset_subclass_status)
        # self.autodataset_worker.stage_updated.connect(self.windowUI.update_autodataset_stage_status)

        self.autodataset_thread.start()
        self.windowUI.autodataset_tab.btn_start.setText("Стоп")
        self.windowUI.autodataset_tab.btn_start.setStyleSheet("background-color: #f44336;")

    def stop_autodataset(self):
        if hasattr(self, "autodataset_worker") and self.autodataset_worker:
            self.autodataset_worker.stop()
        if hasattr(self, "autodataset_thread") and self.autodataset_thread:
            self.autodataset_worker.finished.connect(self.autodataset_thread.quit)
            self.autodataset_thread.finished.connect(self.autodataset_thread.deleteLater)
            self.autodataset_thread = None
        self.windowUI.autodataset_tab.btn_start.setText("Запуск")
        self.windowUI.autodataset_tab.btn_start.setStyleSheet("background-color: #4CAF50;")


def main():
    application = QApplication(sys.argv)
    app = App()
    app.start(application)


if __name__ == "__main__":
    main()