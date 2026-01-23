from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QThread, QUrl
import qdarkstyle
import sys

from project_module.project_manager import Project
from project_module.autodataset import AutoDataset
from project_module.dataset_manager import AVAILABLE_FORMATS
from interface_module.window import MainWindowUI



class App:
    def __init__(self):
        self.autodataset_worker = None
        self.autodataset_thread = None
        self.open_project()


    def new_window(self, project_path: str):
        try:
            if hasattr(self, 'autodataset_worker') and self.autodataset_worker:
                try:
                    if hasattr(self.autodataset_worker, '_is_running') and self.autodataset_worker._is_running:
                        self.stop_autodataset()
                        self.autodataset_worker.close()
                        self.autodataset_worker.deleteLater()
                    self.autodataset_worker = None
                    if hasattr(self, 'autodataset_thread') and self.autodataset_thread:
                        self.autodataset_thread.deleteLater()
                    self.autodataset_thread = None
                except: pass
            self.project_data = Project(project_path)
            self.autodataset_worker = AutoDataset(self.project_data)
            self.windowUI.initUI()
            self.init_config_window()
            self.init_project_conf_in_window()
            self.update_dataset_view_in_window()
            self.windowUI.add_another_program_to_autodataset("chrome.exe")
            self.windowUI.update_autodataset_statuses()
            self.windowUI.show()
        except Exception as e:
            QMessageBox.warning(
                self.windowUI, "Critical error",
                str(e), QMessageBox.StandardButton.Ok)
            self.close_application()
            raise e

    def start(self, app: QApplication):
        self.appApplication = app
        self.appApplication.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
        sys.exit(self.appApplication.exec())

    def close_application(self, event=None):
        if hasattr(self, "appApplication") and hasattr(self, "windowUI") and self.appApplication and self.windowUI:
            self.delete_autodataset_thread()
            if self.autodataset_worker:
                self.autodataset_worker.close()
            self.windowUI.close()
            self.appApplication.quit()
        if event:
            if hasattr(self.windowUI, 'original_close_event'):
                self.windowUI.original_close_event(event)
            else:
                event.accept()


    def init_config_window(self):
        self.windowUI.setWindowTitle(f'{self.windowUI.windowTitle()} ("{self.project_data.project_path}")')
        self.windowUI.project_tab.combo_dataset_format.addItems(AVAILABLE_FORMATS.keys())
        self.windowUI.project_tab.btn_save_project.clicked.connect(self.save_project)
        self.windowUI.dataset_tab.btn_update_dataset.clicked.connect(self.update_dataset_view_in_window)
        self.windowUI.dataset_tab.btn_export_dataset.clicked.connect(self.export_dataset_data)
        self.windowUI.autodataset_tab.work_tab.btn_start.clicked.connect(self.toggle_autodataset_work)
        self.windowUI.actionOpen.triggered.connect(self.open_project)
        self.windowUI.actionSave.triggered.connect(self.save_project)
        self.windowUI.actionSave_As.triggered.connect(self.save_project_as)
        self.windowUI.actionExport.triggered.connect(lambda e: self.export_dataset_data(e, get_path=False))
        self.windowUI.actionExport_As.triggered.connect(self.export_dataset_data)
        self.windowUI.actionExit.triggered.connect(self.close_application)
        # self.windowUI.original_close_event = self.windowUI.closeEvent
        # self.windowUI.closeEvent = self.close_application.__get__(self, type(self.windowUI))

    def init_project_conf_in_window(self):
        project_conf = self.project_data.get_project_conf()
        for clas in project_conf["classes"]:
            cur_class_widget = self.windowUI.project_add_class(clas["class_name"], clas["enabled"])
            for subclas in clas["subclasses"]:
                img_fullpath = self.project_data.get_full_path("example_images", subclas["example_image"])\
                    if subclas["example_image"] else None
                cur_class_widget.add_object(subclas["search_query"], img_fullpath)
        pr_tab = self.windowUI.project_tab
        pr_tab.cb_validation_data.setChecked(project_conf["configuration"]["validation_data"])
        pr_tab.cb_augmented_images.setChecked(project_conf["configuration"]["augmented_images"])
        pr_tab.cb_annotation.setChecked(project_conf["configuration"]["annotation"])
        pr_tab.combo_dataset_format.setCurrentText(project_conf["configuration"]["dataset_format"])
        pr_tab.spin_images_per_class.setValue(project_conf["configuration"]["images_per_class"])
        pr_tab.combo_images_size.setCurrentText(project_conf["configuration"]["images_size"])

    def update_dataset_view_in_window(self):
        classes = self.project_data.get_all_classes_conf()
        for clas in classes:
            class_overview = self.windowUI.dataset_tab.classes_tabs.get(clas["class_name"])
            if not class_overview:
                class_overview = self.windowUI.dataset_add_class(clas["class_name"])
            for type in ["default", "augment", "validation"]:
                type_field = self.windowUI.get_class_field_in_dataset(clas["class_name"], type)
                if not type_field:
                    type_field = self.windowUI.dataset_add_class_field_by_type(clas["class_name"], type)
                    type_field.class_delete_command = lambda e=None, c_id=clas["id"], cw=type_field, t=type, uc=True: [
                        self.project_data.del_image(img["id"]) for img in self.project_data.get_images(c_id, t)]\
                            if self.windowUI.dataset_delete_class_field_widget(cw, uc) else None
                    type_field.class_delete.clicked.disconnect()
                    type_field.class_delete.clicked.connect(type_field.class_delete_command)
                for image in self.project_data.get_images(clas["id"], type):
                    object_widget = type_field.get_object(image["filename"])
                    if not object_widget:
                        object_widget = type_field.add_object(
                            image["filename"], self.project_data.get_full_path("images", image["filename"]))
                        object_widget.object_delete.clicked.disconnect()
                        object_widget.object_delete.clicked.connect(lambda e, img_id=image["id"], cw=type_field, ow=object_widget: (
                            self.project_data.del_image(img_id), cw.delete_object(ow), cw.update_layout()))
                type_field.update_layout()
                type_field.show_class(clas["enabled"])
        classes_names = map(lambda x: x["class_name"], classes)
        for class_name, class_overview in self.windowUI.dataset_tab.classes_tabs.copy().items():
            if not class_name in classes_names:
                for field in class_overview.fields_list:
                    field.class_delete_command(uc=False)
                self.windowUI.dataset_delete_class_overview(class_overview, False)


    def open_project(self, project_path: str=None) -> bool:
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
                    return False
                elif reply == QMessageBox.StandardButton.No:
                    self.open_project()
                    return False
            self.new_window(project_path)
            return True
        else:
            sys.exit()

    def save_project(self):
        pr_tab = self.windowUI.project_tab
        local_project_conf = {
            "configuration": {
                "validation_data": pr_tab.cb_validation_data.isChecked(),
                "augmented_images": pr_tab.cb_augmented_images.isChecked(),
                "annotation": pr_tab.cb_annotation.isChecked(),
                "dataset_format": pr_tab.combo_dataset_format.currentText(),
                "images_per_class": pr_tab.spin_images_per_class.value(),
                "images_size": pr_tab.combo_images_size.currentText()
            },
            "classes_conf": []
        }
        for i, class_obj in enumerate(self.windowUI.project_tab.class_objects):
            local_class = {
                "class_name": class_obj.class_name.text(),
                "enabled": class_obj.class_checkbox.isChecked(),
                "subclasses": []
            }
            for object in class_obj.objects_widgets:
                local_class["subclasses"].append({
                    "search_query": object.object_name.text(),
                    "example_image": object.object_image.my_image_path
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

    def export_dataset_data(self, e=None, get_path=True):
        if get_path:
            dataset_path = QFileDialog.getExistingDirectory(None, "Выберите куда разместить датасет.", "")
        else:
            dataset_path = None
        choiced_format = self.project_data.get_configutation()["dataset_format"]
        DatasetManager = AVAILABLE_FORMATS[choiced_format]
        dataset_manager = DatasetManager.from_project(self.project_data)
        success, message = dataset_manager.export()
        if success:
            QMessageBox.information(self.windowUI, "Успех" if success else "Неудача", message)
            if dataset_path:
                success, message = dataset_manager.put_data(dataset_path)
                if success:
                    QMessageBox.information(self.windowUI, "Успех", message)
            else:
                dataset_path = dataset_manager.get_full_path("dataset")
            url = QUrl.fromLocalFile(dataset_path)
            QDesktopServices.openUrl(url)
        if not success:
            QMessageBox.warning(self.windowUI, "Ошибка", message)


    def toggle_autodataset_work(self):
        if self.autodataset_thread and self.autodataset_thread.isRunning():
            self.stop_autodataset()
        else:
            self.start_autodataset()

    def start_autodataset(self):
        if hasattr(self, 'autodataset_thread') and self.autodataset_thread and self.autodataset_thread.isRunning():
            return
        self.windowUI.setup_autodataset()

        self.delete_autodataset_thread()
        self.autodataset_thread = QThread()
        self.autodataset_worker.moveToThread(self.autodataset_thread)

        self.autodataset_thread.started.connect(self.autodataset_worker.run)
        self.autodataset_worker.finished.connect(self.autodataset_thread.quit)
        self.autodataset_thread.finished.connect(self.on_autodataset_finished)

        self.autodataset_worker.chrome_widget_lock.connect(
            lambda boolean: self.windowUI.autodataset_tab.program_tab.set_lock_resize(boolean))
        self.autodataset_worker.log_field.connect(self.windowUI.autodataset_log)
        self.autodataset_worker.cur_image_label.connect(self.windowUI.autodataset_set_image)
        self.autodataset_worker.stage_updated.connect(self.windowUI.update_autodataset_main_status)
        self.autodataset_worker.subclass_updated.connect(self.windowUI.update_autodataset_object_status)

        self.autodataset_thread.start()
        self.windowUI.set_btn_start_autodataset_state(True)

    def delete_autodataset_thread(self):
        if self.autodataset_thread:
            try:
                self.autodataset_thread.started.disconnect()
                self.autodataset_worker.finished.disconnect()
                self.autodataset_thread.finished.disconnect()
                self.autodataset_worker.chrome_widget_lock.disconnect()
                self.autodataset_worker.log_field.disconnect()
                self.autodataset_worker.cur_image_label.disconnect()
                self.autodataset_worker.stage_updated.disconnect()
                self.autodataset_worker.subclass_updated.disconnect()
            except: pass
        if self.autodataset_worker.thread() != QThread.currentThread():
            self.autodataset_worker.moveToThread(QThread.currentThread())
        if hasattr(self, 'autodataset_thread') and self.autodataset_thread:
            self.autodataset_thread.deleteLater()
            self.autodataset_thread = None

    def on_autodataset_finished(self):
        self.delete_autodataset_thread()
        self.windowUI.set_btn_start_autodataset_state(False)

    def stop_autodataset(self):
        if hasattr(self, 'autodataset_worker') and self.autodataset_worker:
            self.autodataset_worker.stop()



def main():
    application = QApplication(sys.argv)
    app = App()
    app.start(application)



if __name__ == "__main__":
    main()