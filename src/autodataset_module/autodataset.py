from threading import Event, Thread
from time import sleep
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal, Slot, QCoreApplication
from logger import get_logger, LogContext
from project_module.project_manager import Project
from autodataset_module.browser import ChromeBrowser
from autodataset_module.photoshop import *
from autodataset_module.sources import AVAILABLE_SOURCES, DEFAULT_SOURCE, create_source

log = get_logger("autodataset")



class AutoDataset(QObject):
    finished = Signal()
    progress = Signal(int)
    log_field = Signal(str, int)
    cur_image_label = Signal(str, np.ndarray)
    stage_updated = Signal(str, tuple)
    subclass_updated = Signal(str, int, str, int)


    def update_information(self, message: str, level: int = 0,
                           subclass_updated: tuple = None,
                           stage_updated: tuple = None,
                           cur_image: tuple = None):
        if level >= 2:
            log.warning(message)
        elif level == 1:
            log.info("✓ %s", message)
        elif level == 3:
            log.info("⏭ %s", message)
        else:
            log.info(message)
        try:
            self.log_field.emit(message, level)
            if subclass_updated:
                self.subclass_updated.emit(*subclass_updated)
            if stage_updated:
                self.stage_updated.emit(*stage_updated)
            if cur_image:
                self.cur_image_label.emit(*cur_image)
        except:
            print(f"{message}")


    def __init__(self, project_manager: Project, chromedriver_path: str=None,
                 chrome_version: int=None, chrome_no_headless: bool=False, chrome_session: str="default"):
        super().__init__()
        self._is_running = False
        self._stop_event = None
        self._image_downloaded = True
        self.always_switch_to_main_window_thread: Thread = None
        log.info("▶ Initializing AutoDataset (headless=%s, chrome_version=%s)", not chrome_no_headless, chrome_version)

        self.browser = ChromeBrowser(chromedriver_path, chrome_version,
                                     not chrome_no_headless, chrome_session, parent=self)
        self.source = None

        self.project_manager = project_manager
        self.update_project_data()

        self.downloaded_images_count = 0
        self.created_annotations_count = 0
        self.augmented_images_count = 0
        self.need_download_to_class = 0
        self.need_augmented_images_count = 0
        self.all_images_count = 0

        self.do_download_images = True
        self.do_annotation = True
        self.do_augmentation = True

        log.info("✓ AutoDataset initialized (%d classes)", len(self.project_data.get("classes", [])))


    def close(self):
        log.info("▶ Closing AutoDataset")
        self._is_running = False
        if self.source is not None:
            self.source.stop()
            self.source = None
        self.browser.stop()
        log.info("✓ AutoDataset closed")


    def detach_from_thread(self):
        app = QCoreApplication.instance()
        if app is not None and self.thread() != app.thread():
            self.moveToThread(app.thread())


    def always_switch_to_main_window(self):
        while self._is_running and self.browser.is_ready():
            self.browser.switch_to_main_window()
            sleep(0.5)


    def _get_example_image_path(self, subclass_data: dict) -> str | None:
        example_image = subclass_data.get("example_image")
        return self.project_manager.get_full_path("example_images", example_image) if example_image else None


    def download_images(self, subclass_data: dict, class_id: int, num_images: int,
                        num_val_images: int = 0, downloaded: int = 0, to_download: int = 0):
        if num_val_images:
            self.update_information("Validation data enabled", 0)

        self._stop_event = Event()
        collect_stop_event = Event()

        def stop_check() -> bool:
            return self._stop_event.is_set() or not self._is_running

        image_urls = []

        def collect_stop_check() -> bool:
            return stop_check() or collect_stop_event.is_set()

        def collect_url(image_url: str):
            if len(image_urls) < num_images + num_val_images:
                image_urls.append(image_url)
            if len(image_urls) >= num_images + num_val_images:
                collect_stop_event.set()

        try:
            self.source.collect(
                subclass_data, collect_url, collect_stop_check,
                self.update_information, self._get_example_image_path(subclass_data))
        except Exception as e:
            self.update_information(f"Collect error: {e}", 2)
            return

        for image_url in image_urls:
            if stop_check():
                break
            if num_images > 0:
                img_type = "default"
            elif num_val_images > 0:
                img_type = "validation"
            else:
                self._stop_event.set()
                return
            try:
                request = Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(request, timeout=10) as response:
                    image_bytes = response.read()
                image_id = self.project_manager.save_image(image_bytes, class_id, img_type)
                if img_type == "validation":
                    num_val_images -= 1
                else:
                    num_images -= 1
                downloaded += 1
                self.downloaded_images_count += 1
                image_data = self.project_manager.get_image(image_id)
                self.update_information(
                    f"Downloaded {downloaded}/{to_download}. id={image_data['id']} class={image_data['class_id']} file={image_data['filename']}", 0,
                    subclass_updated=(subclass_data["search_query"], downloaded, "", 0),
                    stage_updated=("Download images", (self.downloaded_images_count, self.all_images_count)),
                    cur_image=(self.project_manager.get_full_path("images", image_data["filename"]), np.array([])))
            except Exception as e:
                self.update_information(f"Download error: {e}. src: {image_url}", 2)
            if num_images <= 0 and num_val_images <= 0:
                self._stop_event.set()


    def download_images_data(self):
        source_name = self.project_data["configuration"].get("image_source", DEFAULT_SOURCE)
        self.source = create_source(source_name, self.browser)
        if not self.source:
            self.update_information(
                f"Unknown image source \"{source_name}\". Available: {list(AVAILABLE_SOURCES)}", 2)
            return
        self.update_information(f"Downloading images with source \"{self.source.name}\"...\n", 0)
        for class_data in self.project_data["classes"]:
            for subclass_data in class_data["subclasses"]:
                if class_data["enabled"] and self._is_running:
                    img_counts = round(self.project_data["configuration"]["images_per_class"]/len(class_data["subclasses"]))
                    val_img_counts = (img_counts // 5) if self.project_data["configuration"]["validation_data"] else 0
                    must_img_counts, must_val_img_counts = img_counts, val_img_counts
                    def_count, def_val_count = [round(len(self.project_manager.get_images(
                        class_id=class_data["id"], type=dat_type))/len(class_data["subclasses"])) for dat_type in ["default", "validation"]]
                    img_counts -= def_count; val_img_counts -= def_val_count
                    img_counts, val_img_counts = (img_counts if img_counts>0 else 0), (val_img_counts if val_img_counts>0 else 0)
                    all_imgs = def_count+def_val_count; self.downloaded_images_count += all_imgs; self.update_information(
                        f'Class "{subclass_data["search_query"]}": {all_imgs} existing, need {img_counts} train + {val_img_counts} val', 0,
                        (subclass_data["search_query"], all_imgs, "", 0), ("Download images", (self.downloaded_images_count, self.all_images_count)))
                    if (img_counts or val_img_counts) and (def_count<must_img_counts or def_val_count<must_val_img_counts):
                        self.download_images(subclass_data, class_data["class_id"], img_counts, val_img_counts, all_imgs, must_img_counts+must_val_img_counts)
        self.update_information("Download complete", 1)


    def create_annotation_data(self):
        self.update_information("Creating annotations...\n", 0)
        all_images = []
        for images_type in ["default", "validation"]:
            all_images += self.project_manager.get_images(type=images_type)
        self.all_images_count = len(all_images)
        annotation_configuration = self.project_data["configuration"]
        annotation_classes = [
            class_data for class_data in self.project_data["classes"]
            if class_data["enabled"] and class_data.get("subclasses")
        ]
        annotation_detector = None
        for i, image_data in enumerate(all_images):
            if not self._is_running:
                break
            image_path = self.project_manager.get_full_path("images", image_data["filename"])
            image, new_img_data = open_image(image_path), None
            if not image_data["annotation"]:
                if image is not None and image.size > 0:
                    if annotation_detector is None:
                        annotation_detector = ImageAnnotationDetector(image, annotation_classes, annotation_configuration)
                    else:
                        annotation_detector.image = image
                    annotation_data = annotation_detector.calculate_bboxes_data(
                        allowed_class_ids={image_data["class_id"]})
                    if annotation_data:
                        bboxes = [[item["class_id"]] + list(item["bbox"]) for item in annotation_data]
                        new_img_data = self.project_manager.change_image(image_data["id"], annotation=bboxes)
                    image = annotation_detector.put_contours_on_image(image)
            else:
                image = visualize_bbox(image, image_data["annotation"])
            self.created_annotations_count += 1
            status = "created" if not image_data["annotation"] else "already existed"
            self.update_information(
                f"Annotation #{i+1} {status}. {str(new_img_data or image_data).strip('{}').replace("'", "")}", 0,
                stage_updated=("Create annotation", (self.created_annotations_count, self.all_images_count)),
                cur_image=(image_path, image))
        self.update_information("Annotations complete", 1)


    def create_augmentation_data(self):
        self.update_information("Creating augmentations...\n", 0)
        all_images = self.project_manager.get_images(type="default")
        for i, image_data in enumerate(all_images):
            if not self._is_running:
                break
            image_path = self.project_manager.get_full_path("images", image_data["filename"])
            annotations = list(map(lambda x: x[1:], image_data["annotation"]))
            category_ids = list(map(lambda x: x[0], image_data["annotation"]))
            if not annotations:
                self.update_information(
                    f"Augmentation skipped for image #{i + 1}: no annotations", 2)
                continue
            augmentations = self.project_manager.get_images(parent_image_id=image_data["id"], type="augment")
            if not augmentations:
                augmentations = generate_augmentations(image_path, annotations, category_ids,
                                                    self.project_data["configuration"]["augmentation_count"])
            for j, augmented in enumerate(augmentations):
                if augmented.get("id") is None:
                    bytes_image = cv2.imencode('.jpg', augmented["image"])[1].tobytes()
                    annotation = [[int(cid), *map(int, ann)] for cid, ann in zip(augmented["category_ids"], augmented["bboxes"])]
                    img_id = self.project_manager.save_image(bytes_image, image_data["class_id"], "augment", annotation, image_data["id"])
                    augm_image_data = self.project_manager.get_image(img_id)
                else:
                    augm_image_data = augmented
                preview_image_path = self.project_manager.get_full_path("images", augm_image_data.get("filename") or augmented.get("filename"))
                preview_image = visualize_bbox(augmented.get("image", open_image(preview_image_path)), augm_image_data["annotation"])
                self.augmented_images_count += 1
                status = "already existed" if augmented.get("id") else "created"
                self.update_information(
                    f"Augmentation #{j+1} for image #{i+1} {status}. {str(augm_image_data).strip('{}').replace("'", "")}", 0,
                    stage_updated=("Create augmentation data", (self.augmented_images_count, self.need_augmented_images_count)),
                    cur_image=(preview_image_path, preview_image))
        self.update_information("Augmentations complete", 1)


    def update_project_data(self):
        self.project_data = {
            "configuration": self.project_manager.get_configutation(),
            "classes": self.project_manager.get_all_classes_conf()
        }


    def update_all_information(self, clear: bool=False):
        if not self._is_running:
            self.update_project_data()
            if clear:
                self.downloaded_images_count = 0
                self.created_annotations_count = 0
                self.augmented_images_count = 0
            else:
                self.downloaded_images_count = 0 or self.downloaded_images_count
                self.created_annotations_count = 0 or self.created_annotations_count
                self.augmented_images_count = 0 or self.augmented_images_count
            self.need_download_to_class = int(self.project_data["configuration"]["images_per_class"] *
                                              (1.2 if self.project_data["configuration"]["validation_data"] else 1))
            self.all_images_count = sum([self.need_download_to_class for cl in self.project_data["classes"] if cl["enabled"]])
            self.need_augmented_images_count = sum([self.project_data["configuration"]["images_per_class"]
                                                    for cl in self.project_data["classes"] if cl["enabled"]])\
                                                        * self.project_data["configuration"]["augmentation_count"]

        if self.do_download_images and self.browser.is_ready():
            self.stage_updated.emit("Download images", (self.downloaded_images_count, self.all_images_count))
        for class_data in self.project_data["classes"]:
            if class_data["enabled"]:
                for subclass_data in class_data["subclasses"]:
                    self.subclass_updated.emit(subclass_data["search_query"], 0, class_data["class_name"],
                                               round(self.need_download_to_class/len(class_data["subclasses"])))
        if self.project_data["configuration"]["annotation"] and self.do_annotation:
            self.stage_updated.emit("Create annotation", (self.created_annotations_count, self.all_images_count))
        if self.project_data["configuration"]["augmentation_count"] and self.do_augmentation:
            self.stage_updated.emit("Create augmentation data", (self.augmented_images_count, self.need_augmented_images_count))


    @Slot()
    def run(self):
        self.update_all_information(True)
        self._is_running, self._image_downloaded = True, True
        self.always_switch_to_main_window_thread = None
        self.update_information("AutoDataset run started\n", 0)

        if self.do_download_images:
            self.update_information("Phase 1/3: Starting Chrome...", 0)
            chrome_started = self.browser.start()
            if chrome_started and self.browser.is_ready():
                self.update_information("Phase 1/3: Downloading images...", 0)
                self.update_all_information()
                self.always_switch_to_main_window_thread = Thread(
                    target=self.always_switch_to_main_window, daemon=True)
                self.always_switch_to_main_window_thread.start()
                with LogContext("Download images", log):
                    self.download_images_data()
            else:
                reason = self.browser.last_error or "Chrome start returned without an active driver"
                self.update_information(
                    f"Phase 1/3: Download skipped (Chrome not started): {reason}", 2)
        else:
            self.update_information("Phase 1/3: Download skipped (disabled in settings)", 3)

        if self.project_data["configuration"]["annotation"] and self.do_annotation:
            self.update_information("Phase 2/3: Creating annotations...", 0)
            with LogContext("Create annotations", log):
                self.create_annotation_data()
        else:
            self.update_information("Phase 2/3: Annotation skipped", 3)

        if self.project_data["configuration"]["augmentation_count"] and self.do_augmentation:
            self.update_information("Phase 3/3: Creating augmentations...", 0)
            with LogContext("Create augmentations", log):
                self.create_augmentation_data()
        else:
            self.update_information("Phase 3/3: Augmentation skipped", 3)

        if not self._is_running:
            self.update_information("AutoDataset was stopped by user\n\n\n", 2)
        else:
            self.update_information("AutoDataset finished successfully\n\n\n", 1)

        self._is_running = False
        if self.always_switch_to_main_window_thread:
            self.always_switch_to_main_window_thread.join()
        self.finished.emit()


    @Slot()
    def stop(self):
        self.update_information("User requested stop", 2)
        self._is_running = False
        if self._stop_event:
            self._stop_event.set()