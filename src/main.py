import argparse
import tempfile
import qdarkstyle
from PyQt6.QtCore import QThread, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from autodataset_module.autodataset import AutoDataset
from autodataset_module.photoshop import visualize_bbox, open_image
from interface_module.logs_window import LogsUI
from interface_module.window import MainWindowUI, StatisticsWindow
from logger import get_logger, log_call, LogContext, SessionLogger, install_exception_hook
from pcfuncs import *
from project_module.dataset_manager import AVAILABLE_FORMATS
from project_module.project_manager import Project, get_dataset_statistics

log = get_logger("main")
session = SessionLogger("main")
install_exception_hook(log)



class App:
    @log_call()
    def __init__(self, **config):
        self.config = config
        self.autodataset_worker: AutoDataset | None = None
        self.autodataset_thread: QThread | None = None
        self.appApplication: QApplication | None = None
        self.windowUI: MainWindowUI | None = None
        self.statistics_window: StatisticsWindow | None = None
        self.new_project_temp_dir = None
        self.close_requested = False

        config_info = {k: v for k, v in config.items() if v is not None}
        config_info.pop("project_path", None)
        session.start(extra={"project_path": config["project_path"], **config_info})
        if self.config["project_path"]:
            self.open_project(self.config["project_path"])
        else:
            self.new_project()


    @log_call()
    def start(self, qapp: QApplication):
        log.info("▶ Application starting...")
        exit_code = -1
        try:
            self.appApplication = qapp
            self.appApplication.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
            log.info("✓ QDarkStyle theme applied")
            exit_code = self.appApplication.exec()
            log.info("🏁 Qt event loop exited with code %d", exit_code)
        except Exception as e:
            log.critical("💀 Critical error in event loop: %s", e, exc_info=True)
            QMessageBox.warning(
                self.windowUI, "Critical error",
                str(e), QMessageBox.StandardButton.Ok)
            self.close_application(exit_code)
            raise e

    @log_call()
    def close_application(self, event=None, exit_code: int=0):
        if event and not self.close_requested and self._project_needs_save():
            reply = QMessageBox.question(
                self.windowUI, "Сохранить изменения?", "Сохранить изменения?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Yes:
                if self.new_project_temp_dir is not None:
                    if not self._save_project_as_on_close():
                        event.ignore()
                        return
                else:
                    self.save_project()
        if event:
            event.accept()
        self.close_requested = True
        log.info("✕ Closing application (exit_code=%d)", exit_code)
        session.end(exit_code)

        if self.autodataset_worker:
            log.debug("Closing autodataset worker...")
            self.delete_autodataset_thread()
            self.autodataset_worker.close()
        if self.windowUI and not event:
            log.debug("Closing main window...")
            self.windowUI.close()
        if self.statistics_window:
            log.debug("Closing statistics window...")
            self.statistics_window.close()
        if self.appApplication:
            log.debug("Quitting Qt application...")
            self.appApplication.quit()
        log.info("✓ Application closed (exit_code=%d)", exit_code)
        sys.exit(exit_code)

    @log_call()
    def new_window(self, project_path: str):
        log.info("▶ Opening new window for project: %s", project_path)

        if self.autodataset_worker:
            self.delete_autodataset_thread()
            self.autodataset_worker.close()
            self.autodataset_worker.deleteLater()
            self.autodataset_worker = None

        with LogContext("Project initialization", log):
            self.project_data = Project(project_path)
            log.info("✓ Project loaded: %s classes", len(self.project_data.get_all_classes_conf()))

        with LogContext("AutoDataset initialization", log):
            self.autodataset_worker = AutoDataset(
                self.project_data, self.config["chromedriver_path"],
                self.config["chrome_version"], self.config["chrome_no_headless"])
            log.info("✓ AutoDataset ready (Chrome will be started on demand)")

        with LogContext("UI initialization", log):
            self.windowUI.initUI()
            self.windowUI.closeEvent = self.close_application
            self.init_config_window()
            self.init_project_conf_in_window()
            self.update_dataset_view_in_window()

        self.windowUI.autodataset_update_statuses()
        self.windowUI.show()
        log.info("✓ Window ready for project: %s", project_path)


    def init_config_window(self):
        self.windowUI.setWindowTitle(f'{self.windowUI.windowTitle()} ("{self.project_data.project_path}")')

        self.windowUI.project_tab.combo_dataset_format.addItems(AVAILABLE_FORMATS.keys())
        self.windowUI.project_tab.btn_save_project.clicked.connect(self.save_project)
        self.windowUI.dataset_tab.label_title.clicked.connect(self.open_dataset_information)
        self.windowUI.dataset_tab.btn_update_dataset.clicked.connect(self.update_dataset_view_in_window)
        self.windowUI.dataset_tab.btn_export_dataset.clicked.connect(self.export_dataset_data)
        self.windowUI.autodataset_tab.work_tab.btn_start.clicked.connect(self.toggle_autodataset_work)
        self.autodataset_worker_connect_signals(); at = self.windowUI.autodataset_tab; at.orgShowEvent = at.showEvent
        at.showEvent = lambda e: [at.orgShowEvent(e), self.autodataset_worker.update_all_information()][0]

        self.windowUI.actionNew.triggered.connect(self.new_project)
        self.windowUI.actionOpen.triggered.connect(self.open_project)
        self.windowUI.actionOpen_As_Dir.triggered.connect(self.open_project_as_dir)
        self.windowUI.actionSave.triggered.connect(self.save_project)
        self.windowUI.actionSave_As.triggered.connect(self.save_project_as)
        self.windowUI.actionSave_As_Dir.triggered.connect(self.save_project_as_dir)
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
        pr_tab.cb_validation_data.setChecked(project_conf["configuration"].setdefault("validation_data", False))
        pr_tab.spin_aug_count.setValue(project_conf["configuration"].setdefault("augmentation_count", 0))
        pr_tab.cb_annotation.setChecked(project_conf["configuration"].setdefault("annotation", False))
        pr_tab.combo_dataset_format.setCurrentText(project_conf["configuration"].setdefault("dataset_format", "YOLO"))
        pr_tab.spin_images_per_class.setValue(project_conf["configuration"].setdefault("images_per_class", 100))
        pr_tab.combo_images_size.setCurrentText(project_conf["configuration"].setdefault("images_size", "640x480"))

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
                    field.class_delete.clicked.disconnect()
                    field.class_delete.clicked.connect(
                        lambda e=None, c_id=clas["id"], fw=field, uc=True: self.class_delete_command(c_id, fw, uc))
                    field.class_delete_annotations.clicked.connect(
                        lambda e=None, c_id=clas["id"], fw=field, uc=True: self.class_delete_annotations_command(c_id, fw, uc))
                    field.class_add_object.clicked.disconnect()
                    field.class_add_object.clicked.connect(
                        lambda e=None, c_id=clas["id"], it=images_type: self.import_image_to_class(c_id, it))

                for image in self.project_data.get_images(class_id=clas["id"], type=images_type):
                    object_widget = field.get_object(image["filename"])
                    image_data = self.project_data.get_full_path("images", image["filename"])
                    if image["annotation"] and ((object_widget and object_widget.annotation_data != image["annotation"]) or not object_widget):
                        image_data = visualize_bbox(open_image(image_data), image["annotation"])
                    if not object_widget:
                        object_widget = field.add_object(image["filename"], image_data, False, lambda e: None)
                        object_widget.object_delete.clicked.disconnect()
                        object_widget.object_delete.clicked.connect(
                            lambda e, img_id=image["id"], tf=field, ow=object_widget: (
                                self.project_data.del_image(img_id), tf.delete_object(ow), tf.update_layout()))
                        object_widget.image_data = image.copy()
                    elif object_widget.image_data != image:
                        object_widget.update_object_image(image_data)
                    object_widget.annotation_data = image["annotation"]
                    QApplication.processEvents()

                field.show_class(clas["enabled"])
        self.windowUI.dataset_update_all_class_layouts()

        classes_names = {class_data["class_name"] for class_data in classes}
        for class_name, class_overview in self.windowUI.dataset_tab.classes_tabs.copy().items():
            if not class_name in classes_names:
                for field in class_overview.fields:
                    self.windowUI.dataset_delete_class_field_widget(field, False)
                self.windowUI.dataset_delete_class(class_overview, False)


    def class_delete_command(self, class_id: int | None=None, field_widget=None, user_call: bool=True):
        if not self.windowUI.dataset_delete_class_field_widget(field_widget, user_call):
            return
        log_window = LogsUI("main"); log_window.show()
        log_window.log(f'Удаление изображений из класса id={class_id}, type={field_widget.class_name.text()}...\n')
        QApplication.processEvents()
        try:
            all_images = self.project_data.get_images(class_id=class_id, type=field_widget.class_name.text())
            for i, img in enumerate(all_images):
                self.project_data.del_image(img["id"])
                log_window.log(f'Удалено изображение {img["filename"]} {i+1}/{len(all_images)}.')
                log_window.set_progress(int((i + 1) / len(all_images) * 100))
                QApplication.processEvents()
            log_window.log(f'Успех: изображения удалены из класса id={class_id}, type={field_widget.class_name.text()}.', 1)
        except Exception as e:
            log_window.log(f'Ошибка: {e}', 1)
        finally:
            log_window.wait_while_not_exit()
            self.update_dataset_view_in_window()

    def class_delete_annotations_command(self, class_id: int | None=None, field_widget=None, user_call: bool=True):
        log_window = LogsUI("main"); log_window.show()
        log_window.log(f'Удаление аннотаций из класса id={class_id}, type={field_widget.class_name.text()}...\n')
        QApplication.processEvents()
        try:
            all_images = self.project_data.get_images(class_id=class_id, type=field_widget.class_name.text())
            for i, img in enumerate(all_images):
                self.project_data.change_image(img["id"], annotation=[])
                log_window.log(f'Удалена аннотация изображения {img["filename"]} {i+1}/{len(all_images)}.')
                log_window.set_progress(int((i + 1) / len(all_images) * 100))
                QApplication.processEvents()
            log_window.log(f'Успех: аннотации удалены из класса id={class_id}, type={field_widget.class_name.text()}.', 1)
        except Exception as e:
            log_window.log(f'Ошибка: {e}', 1)
        finally:
            log_window.wait_while_not_exit()
            self.update_dataset_view_in_window()

    def export_images_from_class(self, class_id: int, images_type: str="default", dist_path: str | None=None):
        dist_path = QFileDialog.getExistingDirectory(
            None, "Выберите папку, куда будут скопированы изображения", "") if not dist_path else dist_path
        if not dist_path:
            return
        log_window = LogsUI("main"); log_window.show()
        log_window.log(f'Экспорт изображений из класса id={class_id}, type={images_type} в "{dist_path}"...\n')
        QApplication.processEvents()
        os.makedirs(dist_path, exist_ok=True)
        all_images = self.project_data.get_images(class_id=class_id, type=images_type); total = len(all_images)
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

    def import_image_to_class(self, class_id: int, image_type: str="default", image_path: str | None=None):
        if not image_path:
            image_path, file_types = QFileDialog.getOpenFileName(
                None, "Выберите изображение, которое хотите добавить", "", "Images (*.png *.jpg)")
        else:
            file_types = True
        if file_types and image_path:
            with open(image_path, "rb") as f:
                    self.project_data.save_image(f.read(), class_id, image_type)
            self.update_dataset_view_in_window()

    def import_images_to_class(self, class_id: int, images_type: str="default", images_path: str | None=None):
        images_path = QFileDialog.getExistingDirectory(
            None, "Выберите папку с изображениями, которые хотите импортировать", "") if not images_path else images_path
        if not images_path:
            return
        log_window = LogsUI("main"); log_window.show()
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

    def open_dataset_information(self):
        dataset_information = get_dataset_statistics(self.project_data)
        self.statistics_window = StatisticsWindow()
        self.statistics_window.add_information_batch(dataset_information)
        self.statistics_window.show()


    def new_project(self):
        if self.new_project_temp_dir is not None:
            self.new_project_temp_dir.cleanup()
        self.new_project_temp_dir = tempfile.TemporaryDirectory(prefix="maclearn_new_")
        if self.windowUI is None:
            self.windowUI = MainWindowUI()
        self.new_window(self.new_project_temp_dir.name)

    def _project_needs_save(self) -> bool:
        if self.new_project_temp_dir is not None:
            return True
        if not self.windowUI or not getattr(self, "project_data", None):
            return False
        current = self._get_project_configuration()
        saved = self.project_data.get_project_conf()
        return (
            current["configuration"] != saved["configuration"] or
            self._normalize_classes(current["classes_conf"]) !=
            self._normalize_classes(saved["classes"])
        )

    @staticmethod
    def _normalize_classes(classes: list) -> list:
        normalized = []
        for class_data in classes:
            normalized.append({
                "class_id": class_data.get("class_id", class_data.get("id")),
                "class_name": class_data["class_name"],
                "enabled": class_data["enabled"],
                "subclasses": [{
                    "search_query": subclass["search_query"],
                    "example_image": os.path.basename(subclass["example_image"])
                    if subclass.get("example_image") else None
                } for subclass in class_data["subclasses"]]
            })
        return normalized

    def _save_project_as_on_close(self) -> bool:
        project_path, ok = QFileDialog.getSaveFileName(
            self.windowUI, "Сохранить проект как", "Новый проект.maclproj",
            "MacLearn Project (*.maclproj)")
        if not ok or not project_path:
            return False
        if not project_path.endswith(".maclproj"):
            project_path += ".maclproj"
        status, message = self.project_data.save_as(project_path)
        if not status:
            QMessageBox.warning(self.windowUI, "Ошибка", message)
            return False
        self.new_project_temp_dir.cleanup()
        self.new_project_temp_dir = None
        return True

    def _get_project_configuration(self) -> dict:
        pr_tab = self.windowUI.project_tab
        classes_conf = []
        for class_obj in pr_tab.project_overview.fields:
            subclasses = [{
                "search_query": object.object_name.text(),
                "example_image": object.object_image.my_image_path
            } for object in class_obj.objects]
            classes_conf.append({
                "class_id": class_obj.class_data["id"] if hasattr(class_obj, "class_data") else None,
                "class_name": class_obj.class_name.text(),
                "enabled": class_obj.class_checkbox.isChecked(),
                "subclasses": subclasses
            })
        return {
            "configuration": {
                "validation_data": pr_tab.cb_validation_data.isChecked(),
                "augmentation_count": pr_tab.spin_aug_count.value(),
                "annotation": pr_tab.cb_annotation.isChecked(),
                "dataset_format": pr_tab.combo_dataset_format.currentText(),
                "images_per_class": pr_tab.spin_images_per_class.value(),
                "images_size": pr_tab.combo_images_size.currentText()
            },
            "classes_conf": classes_conf
        }

    def open_project_as_dir(self) -> bool | None:
        project_path = QFileDialog.getExistingDirectory(None, "Выберите папку проекта", "")
        if project_path:
            return self.open_project(project_path)
        else: return None

    def open_project(self, project_path: str | None=None) -> bool:
        if not project_path:
            project_path, _ = QFileDialog.getOpenFileName(
                self.windowUI, "Открыть проект", "", "MacLearn Project (*.maclproj)")
        if project_path:
            previous_window = self.windowUI
            self.windowUI = MainWindowUI()
            if not Project.path_is_project(project_path):
                reply = QMessageBox.question(
                    previous_window or self.windowUI, "Проект не найден или повреждён",
                    f'Проект по заданному пути "{project_path}" не найден, или повреждён. '+\
                        'Будут созданы недостающие папки и файлы.',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    self.windowUI.deleteLater()
                    self.windowUI = previous_window
                    return False
            if self.new_project_temp_dir is not None:
                self.new_project_temp_dir.cleanup()
                self.new_project_temp_dir = None
            self.new_window(project_path)
            if previous_window:
                previous_window.closeEvent = lambda event: event.accept()
                previous_window.close()
                previous_window.deleteLater()
            return True
        elif not self.windowUI:
            sys.exit()
        else:
            return False

    def save_project(self):
        self.project_data.save(**self._get_project_configuration())
        self.windowUI.autodataset_update_statuses()

    def save_project_as(self):
        new_project_path, ok = QFileDialog.getSaveFileName(
            self.windowUI, "Сохранить проект как", "", "MacLearn Project (*.maclproj)")
        if not ok or not new_project_path:
            return
        if not new_project_path.endswith('.maclproj'):
            new_project_path += '.maclproj'
        status, message = self.project_data.save_as(new_project_path)
        if status:
            QMessageBox.information(self.windowUI, "Успех", message)
            reply = QMessageBox.question(
                self.windowUI, "Перезапуск в новом проекте",
                f'Перезапустить окно в новом проекте "{new_project_path}"?.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.open_project(new_project_path)
        else:
            QMessageBox.warning(self.windowUI, "Ошибка", message)

    def save_project_as_dir(self):
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

    def export_dataset_data(self, e=None):
        dataset_path = QFileDialog.getExistingDirectory(None, "Выберите куда разместить датасет.", "")
        if not dataset_path:
            return
        choiced_format = self.project_data.get_configutation()["dataset_format"]
        DatasetManager = AVAILABLE_FORMATS[choiced_format]
        dataset_manager = DatasetManager.from_project(self.project_data)
        success, message = dataset_manager.export()
        if success:
            QMessageBox.information(self.windowUI, "Успех", message)
            success, message = dataset_manager.put_data(dataset_path)
            if success:
                QMessageBox.information(self.windowUI, "Успех", message)
            QDesktopServices.openUrl(QUrl.fromLocalFile(dataset_path))
        if not success:
            QMessageBox.warning(self.windowUI, "Ошибка", message)
        dataset_manager.clear()


    def toggle_autodataset_work(self):
        if self.autodataset_worker and self.autodataset_worker._is_running:
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
        self.autodataset_worker.finished.connect(self.autodataset_worker.detach_from_thread)
        self.autodataset_thread.finished.connect(self.on_autodataset_finished)
        self.autodataset_worker_connect_signals()

        self.autodataset_thread.start()
        self.windowUI.set_btn_start_autodataset_state(True)

    def autodataset_worker_disconnect_signals(self):
        signals = (
            self.autodataset_worker.browser.ready,
            self.autodataset_worker.browser.chrome_widget_lock,
            self.autodataset_worker.log_field,
            self.autodataset_worker.cur_image_label,
            self.autodataset_worker.stage_updated,
            self.autodataset_worker.subclass_updated,
        )
        for signal in signals:
            try:
                signal.disconnect()
            except TypeError:
                pass

    def autodataset_worker_connect_signals(self):
        self.autodataset_worker_disconnect_signals()
        if not self.autodataset_worker.browser.chrome_headless:
            self.autodataset_worker.browser.ready.connect(self.windowUI.autodataset_embed_chrome)
        self.autodataset_worker.browser.chrome_widget_lock.connect(self.windowUI.autodataset_set_chrome_lock)
        self.autodataset_worker.log_field.connect(self.windowUI.autodataset_log)
        self.autodataset_worker.cur_image_label.connect(self.windowUI.autodataset_set_image)
        self.autodataset_worker.stage_updated.connect(self.windowUI.update_autodataset_main_status)
        self.autodataset_worker.subclass_updated.connect(self.windowUI.autodataset_set_object_status)

    def delete_autodataset_thread(self):
        if self.autodataset_thread:
            signals = (self.autodataset_thread.started, self.autodataset_worker.finished,
                       self.autodataset_thread.finished)
            for signal in signals:
                try:
                    signal.disconnect()
                except TypeError:
                    pass
        if self.autodataset_worker.thread() != QThread.currentThread():
            self.autodataset_worker.moveToThread(QThread.currentThread())
        if self.autodataset_thread:
            self.autodataset_thread.deleteLater()
            self.autodataset_thread = None

    def on_autodataset_finished(self):
        self.delete_autodataset_thread()
        self.windowUI.set_btn_start_autodataset_state(False)
        notify(message='Автодатасет закончил свою работу. Датасет готов к использованию.',
               app_name='MacLearn', title='MacLearn автодатасет')

    def stop_autodataset(self):
        if self.autodataset_worker and self.autodataset_worker._is_running:
            self.autodataset_worker.stop()



def main():
    global app, application

    arg_parser = argparse.ArgumentParser(
        "MacLearn", description="A program that will automatically assemble a "+
        "high-quality dataset of thousands of images for you in a matter of minutes.")
    arg_parser.add_argument("--project-path", nargs='?', default=None,
                            help="path of your MacLearn project (skip this to create a new project)")
    arg_parser.add_argument("--chrome-version", type=int, default=None,
                            help="version of Chrome installed on your computer (you can skip this, if the program is working fine)")
    arg_parser.add_argument("--chromedriver-path", type=str, default=None,
                            help="path to your chromedriver (you can skip this, if the program is working fine)")
    arg_parser.add_argument("--chrome-no-headless", action='store_true', default=False,
                            help="if you want to see the browser, enable this feature")
    arguments = arg_parser.parse_args()

    application = QApplication(sys.argv)
    app = App(**dict(arguments._get_kwargs()))
    app.start(application)



if __name__ == "__main__":
    main()