from project_manager import Project
from window import MainWindowUI
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
import sys



class App:
    def __init__(self):
        self.open_project()

    def start(self, app):
        self.appApplication = app
        sys.exit(self.appApplication.exec())

    def close_application(self):
        if hasattr(self, "appApplication") and hasattr(self, "windowUI"):
            self.windowUI.close()
            self.appApplication.quit()


    def config_window(self):
        self.windowUI.setWindowTitle(f'{self.windowUI.windowTitle()} ("{self.project_data.project_path}")')
        self.windowUI.project_tab.btn_save_project.clicked.connect(self.save_project)
        self.windowUI.actionOpen.triggered.connect(self.open_project)
        self.windowUI.actionSave.triggered.connect(self.save_project)
        self.windowUI.actionSave_As.triggered.connect(self.save_project_as)
        self.windowUI.actionExit.triggered.connect(self.close_application)

    def init_project_conf_in_window(self):
        project_conf = self.project_data.get_project_conf()
        for clas in project_conf["classes"]:
            cur_class_widget = self.windowUI.add_class(clas["class_name"], clas["enabled"])
            for subclas in clas["subclasses"]:
                img_fullpath = self.project_data.get_full_path("example_images", subclas["example_image"])\
                    if subclas["example_image"] else None
                self.windowUI.add_subclass(
                    cur_class_widget, subclas["search_query"], img_fullpath)
        pr_tab = self.windowUI.project_tab
        pr_tab.cb_validation_data.setChecked(project_conf["configuration"]["validation_data"])
        pr_tab.cb_augmented_images.setChecked(project_conf["configuration"]["augmented_images"])
        pr_tab.cb_annotation.setChecked(project_conf["configuration"]["annotation"])
        pr_tab.combo_annotation_format.setCurrentText(project_conf["configuration"]["annotation_format"])
        pr_tab.spin_images_per_class.setValue(project_conf["configuration"]["images_per_class"])


    def open_project(self, project_path: str = None) -> bool:
        if not project_path:
            project_path = QFileDialog.getExistingDirectory(
                None, "Выберите папку проекта", "")
        if project_path:
            if hasattr(self, 'windowUI') and self.windowUI:
                self.windowUI.close()
                self.windowUI.deleteLater()
            self.windowUI = MainWindowUI()
            if not Project.path_is_project(project_path):
                reply = QMessageBox.question(
                    self.windowUI, "Проект не найден или повреждён",
                    f'Проект по заданному пути "{project_path}" не найден, или повреждён. '+\
                        'Будут созданы недостающие папки и файлы.',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Close:
                    self.close_application()
                elif reply == QMessageBox.StandardButton.No:
                    self.open_project()
                    return
            self.project_data = Project(project_path)
            self.windowUI.initUI()
            self.config_window()
            self.init_project_conf_in_window()
            self.windowUI.update_autodataset_statuses()
            self.windowUI.show()

    def save_project(self):
        pr_tab = self.windowUI.project_tab
        local_project_conf = {
            "configuration": {
                "validation_data": pr_tab.cb_validation_data.isChecked(),
                "augmented_images": pr_tab.cb_augmented_images.isChecked(),
                "annotation": pr_tab.cb_annotation.isChecked(),
                "annotation_format": pr_tab.combo_annotation_format.currentText(),
                "images_per_class": pr_tab.spin_images_per_class.value()
            },
            "classes_conf": []
        }
        for i, class_obj in enumerate(self.windowUI.project_tab.class_objects):
            local_class = {
                "class_name": class_obj.class_name.text(),
                "enabled": class_obj.class_checkbox.isChecked(),
                "subclasses": []
            }
            for subclass in class_obj.subclass_widgets:
                local_class["subclasses"].append({
                    "search_query": subclass.object_name.text(),
                    "example_image": subclass.object_image.my_image_path
                })
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



def main():
    application = QApplication(sys.argv)
    app = App()
    app.start(application)



if __name__ == "__main__":
    main()