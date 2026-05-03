from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QThread, QUrl
import qdarkstyle
import subprocess
import argparse
import shutil
import sys
import os

from project_module.project_manager import Project
from project_module.autodataset import AutoDataset
from project_module.dataset_manager import AVAILABLE_FORMATS
from interface_module.window import MainWindowUI
from interface_module.logs_window import LogsUI
from project_module.photoshop import visualize_bbox, open_image



def launch_new_instance():
    if getattr(sys, 'frozen', False):
        executable, args = sys.argv[0], sys.argv[1:]
    else:
        executable, args = sys.executable, sys.argv
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        subprocess.Popen(
            [executable] + args,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            startupinfo=startupinfo, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True)
    else:
        subprocess.Popen(
            [executable] + args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)



class App:
    def __init__(self, **config):
        self.config = config
        self.autodataset_worker: AutoDataset = None
        self.autodataset_thread: QThread = None
        self.appApplication: QApplication = None
        self.windowUI: MainWindowUI = None
        self.open_project(self.config["project_path"])


    def start(self, app: QApplication):
        exit_code = -1
        try:
            self.appApplication = app
            self.appApplication.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
            exit_code = self.appApplication.exec()
        except Exception as e:
            QMessageBox.warning(
                self.windowUI, "Critical error",
                str(e), QMessageBox.StandardButton.Ok)
            self.close_application(exit_code)
            raise e

    def close_application(self, event=None, exit_code: int=0):
        if self.autodataset_worker:
            self.delete_autodataset_thread()
            self.autodataset_worker.close()
        if self.appApplication and self.windowUI:
            self.windowUI.close()
            self.appApplication.quit()
        if event:
            if hasattr(self.windowUI, 'original_close_event'):
                self.windowUI.original_close_event(event)
            else:
                event.accept()
        sys.exit(exit_code)


    def new_window(self, project_path: str):
        if self.autodataset_worker:
            try:
                self.delete_autodataset_thread()
                self.autodataset_worker.close()
            except: pass
            self.autodataset_worker.deleteLater()
            self.autodataset_worker = None
        self.project_data = Project(project_path)
        self.autodataset_worker = AutoDataset(
            self.project_data, self.config["chromedriver_path"], self.config["chrome_version"], self.config["chrome_headless"])
        self.windowUI.initUI()
        self.init_config_window()
        self.init_project_conf_in_window()
        self.update_dataset_view_in_window()
        if self.autodataset_worker.driver and not self.autodataset_worker.chrome_headless:
            self.windowUI.add_another_program_to_autodataset("chrome.exe", self.autodataset_worker.chrome_pid)
        self.windowUI.autodataset_update_statuses()
        self.windowUI.show()


    def init_config_window(self):
        self.windowUI.setWindowTitle(f'{self.windowUI.windowTitle()} ("{self.project_data.project_path}")')
        self.windowUI.project_tab.combo_dataset_format.addItems(AVAILABLE_FORMATS.keys())
        self.windowUI.project_tab.btn_save_project.clicked.connect(self.save_project)
        self.windowUI.dataset_tab.btn_update_dataset.clicked.connect(self.update_dataset_view_in_window)
        self.windowUI.dataset_tab.btn_export_dataset.clicked.connect(self.export_dataset_data)
        self.windowUI.autodataset_tab.work_tab.btn_start.clicked.connect(self.toggle_autodataset_work)
        self.autodataset_worker_connect_signals(); at = self.windowUI.autodataset_tab; at.orgShowEvent = at.showEvent
        at.showEvent = lambda e: [at.orgShowEvent(e), self.autodataset_worker.update_all_information()][0]

        self.windowUI.actionOpen.triggered.connect(self.open_project)
        self.windowUI.actionSave.triggered.connect(self.save_project)
        self.windowUI.actionSave_As.triggered.connect(self.save_project_as)
        self.windowUI.actionExport.triggered.connect(lambda e: self.export_dataset_data(e, get_path=False))
        self.windowUI.actionExport_As.triggered.connect(self.export_dataset_data)
        self.windowUI.actionRestart.triggered.connect(lambda e: self.open_project(self.project_data.project_path))
        self.windowUI.actionNewWindow.triggered.connect(launch_new_instance)
        self.windowUI.actionExit.triggered.connect(self.close_application)
        self.windowUI.actionOpenAbout.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/b1t0nese/MacLearn")))

    def init_project_conf_in_window(self):
        project_conf = self.project_data.get_project_conf()
        for clas in project_conf["classes"]:
            cur_class_widget = self.windowUI.project_add_class(clas["class_name"], clas["enabled"])
            cur_class_widget.class_data = clas.copy()
            for subclas in clas["subclasses"]:
                img_fullpath = self.project_data.get_full_path("example_images", subclas["example_image"])\
                    if subclas["example_image"] else None
                cur_class_widget.add_object(subclas["search_query"], img_fullpath)
        pr_tab = self.windowUI.project_tab
        pr_tab.cb_validation_data.setChecked(project_conf["configuration"]["validation_data"])
        pr_tab.cb_augmented_images.setChecked(project_conf["configuration"]["augmentation"])
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

            for images_type in ["default", "augment", "validation"]:
                field = self.windowUI.get_class_field_in_dataset(clas["class_name"], images_type)
                if not field:
                    field = self.windowUI.dataset_add_class_field(clas["class_name"], images_type)
                    field.class_import_files.clicked.connect(
                        lambda e=None, c_id=clas["id"], it=images_type: self.import_images_to_class(c_id, it))
                    field.class_export_files.clicked.connect(
                        lambda e=None, c_id=clas["id"], it=images_type: self.export_images_from_class(c_id, it))
                    field.class_delete.clicked.disconnect(); field.class_delete.clicked.connect(
                        lambda e=None, c_id=clas["id"], fw=field, uc=True: self.class_delete_command(c_id, fw, uc))
                    field.class_add_object.clicked.disconnect(); field.class_add_object.clicked.connect(
                        lambda e=None, c_id=clas["id"], it=images_type: self.import_image_to_class(c_id, it))

                for image in self.project_data.get_images(clas["id"], images_type):
                    object_widget = field.get_object(image["filename"])
                    image_data = self.project_data.get_full_path("images", image["filename"])
                    if image["annotation"]:
                        image_data = visualize_bbox(open_image(image_data), image["annotation"])
                    if not object_widget:
                        object_widget = field.add_object(image["filename"], image_data, False, lambda e: None)
                        object_widget.object_delete.clicked.disconnect(); object_widget.object_delete.clicked.connect(
                            lambda e, img_id=image["id"], tf=field, ow=object_widget: (
                                self.project_data.del_image(img_id), tf.delete_object(ow), tf.update_layout()))
                        object_widget.image_data = image.copy()
                    elif object_widget.image_data != image:
                        object_widget.update_object_image(image_data)

                field.show_class(clas["enabled"])
        self.windowUI.dataset_update_all_class_layouts()

        classes_names = map(lambda x: x["class_name"], classes)
        for class_name, class_overview in self.windowUI.dataset_tab.classes_tabs.copy().items():
            if not class_name in classes_names:
                for field in class_overview.fields:
                    self.windowUI.dataset_delete_class_field_widget(field, False)
                self.windowUI.dataset_delete_class(class_overview, False)


    def class_delete_command(self, class_id: int=None, field_widget=None, user_call: bool=True):
        if not self.windowUI.dataset_delete_class_field_widget(field_widget, user_call):
            return
        log_window = LogsUI(); log_window.show()
        log_window.log(f'Удаление изображений из класса id={class_id}, type={field_widget.class_name.text()}...\n')
        QApplication.processEvents()
        try:
            all_images = self.project_data.get_images(class_id, field_widget.class_name.text()); total = len(all_images)
            for i, img in enumerate(all_images):
                self.project_data.del_image(img["id"])
                log_window.log(f'Удалено изображение {img["filename"]} {i+1}/{total}.')
                log_window.set_progress(int((i + 1) / total * 100))
                QApplication.processEvents()
            log_window.log(f'Успех: изображения удалены из класса id={class_id}, type={field_widget.class_name.text()}.', 1)
        except Exception as e:
            log_window.log(f'Ошибка: {e}', 1)
        finally:
            log_window.wait_while_not_exit()
            self.update_dataset_view_in_window()

    def export_images_from_class(self, class_id: int, images_type: str="default", dist_path: str=None):
        dist_path = QFileDialog.getExistingDirectory(
            None, "Выберите папку, куда будут скопированы изображения", "") if not dist_path else dist_path
        if not dist_path:
            return
        log_window = LogsUI(); log_window.show()
        log_window.log(f'Экспорт изображений из класса id={class_id}, type={images_type} в "{dist_path}"...\n')
        QApplication.processEvents()
        os.makedirs(dist_path, exist_ok=True)
        all_images = self.project_data.get_images(class_id, images_type); total = len(all_images)
        try:
            for i, image_data in enumerate(all_images):
                image_path = self.project_data.get_full_path("images", image_data["filename"])
                dist_image_path = os.path.join(dist_path, os.path.basename(image_path))
                shutil.copy2(image_path, dist_image_path)
                log_window.log(f'Экспортировано изображение {i+1}/{total}: {os.path.basename(image_path)} в {dist_image_path}.')
                log_window.set_progress(int((i + 1) / total * 100))
                QApplication.processEvents()
            log_window.log(f'Успех: изображения скопированы в {dist_path}.', 1)
        except Exception as e:
            log_window.log(f'Ошибка: {e}', 1)
        finally:
            log_window.wait_while_not_exit()
            QDesktopServices.openUrl(QUrl.fromLocalFile(dist_path))

    def import_image_to_class(self, class_id: int, image_type: str="default", image_path: str=None):
        image_path, file_types = QFileDialog.getOpenFileName(
            None, "Выберите изображение, которое хотите добавить", "", "Images (*.png *.jpg)") if not image_path else image_path
        if file_types and image_path:
            with open(image_path, "rb") as f:
                    self.project_data.save_image(f.read(), class_id, image_type)
            self.update_dataset_view_in_window()

    def import_images_to_class(self, class_id: int, images_type: str = "default", images_path: str = None):
        images_path = QFileDialog.getExistingDirectory(
            None, "Выберите папку с изображениями, которые хотите импортировать", "") if not images_path else images_path
        if not images_path:
            return
        log_window = LogsUI(); log_window.show()
        log_window.log(f'Импорт изображений в класс id={class_id}, type={images_type} из "{images_path}"...\n')
        QApplication.processEvents()
        images_paths = os.listdir(images_path); total = len(images_paths)
        try:
            for i, image_name in enumerate(images_paths):
                image_path = os.path.join(images_path, image_name)
                with open(image_path, "rb") as f:
                    self.project_data.save_image(f.read(), class_id, images_type)
                log_window.log(f'Импортировано изображение {i+1}/{total}: {image_name} в "{image_path}".')
                log_window.set_progress(int((i + 1) / total * 100))
                QApplication.processEvents()
            log_window.log(f'Успех: изображения скопированы в класс id={class_id}, type={images_type} из "{images_path}".', 1)
        except Exception as e:
            log_window.log(f'Ошибка: {e}', 1)
        finally:
            log_window.wait_while_not_exit()
            self.update_dataset_view_in_window()

    def open_project(self, project_path: str=None) -> bool:
        if not project_path:
            project_path = QFileDialog.getExistingDirectory(
                None, "Выберите папку проекта", "")
        if project_path:
            if self.windowUI:
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
        elif not self.windowUI:
            sys.exit()
        else:
            return False

    def save_project(self):
        pr_tab = self.windowUI.project_tab
        local_project_conf = {
            "configuration": {
                "validation_data": pr_tab.cb_validation_data.isChecked(),
                "augmentation": pr_tab.cb_augmented_images.isChecked(),
                "annotation": pr_tab.cb_annotation.isChecked(),
                "dataset_format": pr_tab.combo_dataset_format.currentText(),
                "images_per_class": pr_tab.spin_images_per_class.value(),
                "images_size": pr_tab.combo_images_size.currentText()
            },
            "classes_conf": []
        }
        for class_obj in self.windowUI.project_tab.project_overview.fields:
            local_class = {
                "class_id": class_obj.class_data["id"] if hasattr(class_obj, "class_data") else None,
                "class_name": class_obj.class_name.text(),
                "enabled": class_obj.class_checkbox.isChecked(),
                "subclasses": []
            }
            for object in class_obj.objects:
                local_class["subclasses"].append({
                    "search_query": object.object_name.text(),
                    "example_image": object.object_image.my_image_path
                })
            local_project_conf["classes_conf"].append(local_class)
        self.project_data.save(**local_project_conf)
        self.windowUI.autodataset_update_statuses()

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
            dataset_path = QFileDialog.getExistingDirectory(None, "Выберите куда разместить датасет (можно пропустить закрыв окно).", "")
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
            QDesktopServices.openUrl(QUrl.fromLocalFile(dataset_path))
        if not success:
            QMessageBox.warning(self.windowUI, "Ошибка", message)


    def toggle_autodataset_work(self):
        if self.autodataset_thread and self.autodataset_thread.isRunning():
            self.stop_autodataset()
        else:
            self.start_autodataset()

    def start_autodataset(self):
        if self.autodataset_thread and self.autodataset_thread.isRunning():
            return
        self.windowUI.setup_autodataset()
        self.autodataset_worker.do_download_images = self.windowUI.autodataset_tab.work_tab.check_download.isChecked()
        self.autodataset_worker.do_annotation = self.windowUI.autodataset_tab.work_tab.check_annotation.isChecked()
        self.autodataset_worker.do_augmentation = self.windowUI.autodataset_tab.work_tab.check_augmentation.isChecked()

        self.delete_autodataset_thread()
        self.autodataset_thread = QThread()
        self.autodataset_worker.moveToThread(self.autodataset_thread)

        self.autodataset_thread.started.connect(self.autodataset_worker.run)
        self.autodataset_worker.finished.connect(self.autodataset_thread.quit)
        self.autodataset_thread.finished.connect(self.on_autodataset_finished)
        self.autodataset_worker_connect_signals()

        self.autodataset_thread.start()
        self.windowUI.set_btn_start_autodataset_state(True)

    def autodataset_worker_disconnect_signals(self):
        try:
            if self.autodataset_worker.driver and not self.autodataset_worker.chrome_headless:
                self.autodataset_worker.chrome_widget_lock.disconnect()
            self.autodataset_worker.log_field.disconnect()
            self.autodataset_worker.cur_image_label.disconnect()
            self.autodataset_worker.stage_updated.disconnect()
            self.autodataset_worker.subclass_updated.disconnect()
        except: pass

    def autodataset_worker_connect_signals(self):
        self.autodataset_worker_disconnect_signals()
        if self.autodataset_worker.driver and not self.autodataset_worker.chrome_headless:
            self.autodataset_worker.chrome_widget_lock.connect(
                lambda boolean: self.windowUI.autodataset_tab.program_tab.set_lock_resize(boolean))
        self.autodataset_worker.log_field.connect(self.windowUI.autodataset_log)
        self.autodataset_worker.cur_image_label.connect(self.windowUI.autodataset_set_image)
        self.autodataset_worker.stage_updated.connect(self.windowUI.update_autodataset_main_status)
        self.autodataset_worker.subclass_updated.connect(self.windowUI.autodataset_set_object_status)

    def delete_autodataset_thread(self):
        if self.autodataset_thread:
            try:
                self.autodataset_thread.started.disconnect()
                self.autodataset_worker.finished.disconnect()
                self.autodataset_thread.finished.disconnect()
            except: pass
        if self.autodataset_worker.thread() != QThread.currentThread():
            self.autodataset_worker.moveToThread(QThread.currentThread())
        if self.autodataset_thread:
            self.autodataset_thread.deleteLater()
            self.autodataset_thread = None

    def on_autodataset_finished(self):
        self.delete_autodataset_thread()
        self.windowUI.set_btn_start_autodataset_state(False)

    def stop_autodataset(self):
        if self.autodataset_worker:
            self.autodataset_worker.stop()



def main():
    global app, application

    arg_parser = argparse.ArgumentParser(
        "MacLearn", description="A program that will automatically assemble a "+
        "high-quality dataset of thousands of images for you in a matter of minutes.")
    arg_parser.add_argument("--project-path", type=str, default=None,
                            help="path of your MacLearn project (skip this to choice project from explorer)")
    arg_parser.add_argument("--chrome-version", type=int, default=None,
                            help="version of Chrome installed on your computer (you can skip this, if the program is working fine)")
    arg_parser.add_argument("--chromedriver-path", type=str, default=None,
                            help="path to your chromedriver (you can skip this, if the program is working fine)")
    arg_parser.add_argument("-chrome-headless", action='store_true', default=False,
                            help="if you don't want to see the browser, enable this feature")
    arguments = arg_parser.parse_args()

    application = QApplication(sys.argv)
    app = App(**dict(arguments._get_kwargs()))
    app.start(application)



if __name__ == "__main__":
    main()