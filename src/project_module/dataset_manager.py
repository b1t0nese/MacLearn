from pathlib import Path
import datetime
import getpass
import shutil
import yaml
import csv
import cv2
import os

from .project_manager import Project
from .photoshop import *



class BaseDataset(Project):
    @classmethod
    def from_project(cls, project: Project):
        instance = cls.__new__(cls)
        instance.__dict__.update(project.__dict__)
        instance.add_skipped_paths()
        return instance

    def __init__(self, project_path: str):
        super().__init__(project_path)
        self.add_skipped_paths()

    def clear(self):
        try:
            del self.project_paths["dataset"]
            shutil.rmtree(self.get_full_path("dataset"))
        except: pass


    def put_data(self, dataset_path: str) -> tuple[bool, str]:
        try:
            if os.path.exists(dataset_path):
                shutil.rmtree(dataset_path)
            os.makedirs(dataset_path, exist_ok=True)
            source_dir = self.get_full_path("dataset")
            for item in os.listdir(source_dir):
                source_item = os.path.join(source_dir, item)
                dest_item = os.path.join(dataset_path, item)
                if os.path.isdir(source_item):
                    shutil.copytree(source_item, dest_item, dirs_exist_ok=True)
                else:
                    shutil.copy2(source_item, dest_item)
            return True, f"Датасет успешно перемещён по пути: {dataset_path}"
        except Exception as e:
            return False, f"Датасет не был перемещён по новому пути. Ошибка: {e}"


    def get_dataset_path(self) -> str:
        proj_path = Path(self.project_path)
        if proj_path.is_file() and proj_path.suffix == '.maclproj':
            base_name = proj_path.stem
            parent_dir = proj_path.parent
        else:
            base_name = proj_path.name
            parent_dir = proj_path.parent
        dataset_dir_name = f"{base_name}_dataset"
        return str(parent_dir / dataset_dir_name)



AVAILABLE_FORMATS: dict[str, BaseDataset] = {}

def register_formatter(name):
    def decorator(cls):
        AVAILABLE_FORMATS[name] = cls
        return cls
    return decorator



def export_image(first_path: str, dist_path: str, resize_size: tuple=None):
    if os.path.exists(dist_path):
        os.remove(dist_path)
    image = open_image(first_path, None)
    if resize_size:
        image = resize_image(image, resize_size)
    _, encoded_image = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    with open(dist_path, 'wb') as f:
        f.write(encoded_image.tobytes())



@register_formatter("YOLO")
class YOLOdataset(BaseDataset):
    def create_paths(self, classes_len: int=0, annotation: bool=False):
        self.project_paths["dataset"] = {
            "train": {},
            "val": {},
            "data.yaml": None
        }
        for p1 in ["train", "val"]:
            for p2 in map(str, range(classes_len)):
                self.project_paths["dataset"][p1][p2] = {}
                if annotation:
                    self.project_paths["dataset"][p1][p2]["labels"] = {}
        self.makedirs_ifnotexc()


    def create_yaml_config(self, classes_config: list=[]):
        if not classes_config:
            classes_config = self.get_all_classes_conf(True)
        yaml_content = {
            'path': ".",
            'train': 'train',
            'val': 'val',
            'nc': len(classes_config),
            'names': list(map(lambda x: x["class_name"], classes_config)),
            'author': getpass.getuser(),
            'date': datetime.datetime.now().strftime('%Y-%m-%d'),
            'description': 'Dataset created with MacLearn https://github.com/b1t0nese/MacLearn'
        }
        with open(self.get_full_path("dataset", "data.yaml"), 'w', encoding="utf-8") as f:
            yaml.dump(yaml_content, f, default_flow_style=False, allow_unicode=True)


    def export_data(self, classes_config: list=[], images_size: str="320x240"):
        if not classes_config:
            classes_config = self.get_all_classes_conf(True)
        for i, clas in enumerate(classes_config):
            class_images = self.get_images(class_id=clas["id"])
            for image in class_images:
                image_path = self.get_full_path("images", image["filename"])
                class_path = self.get_full_path("dataset", "train" if not image["type"]=="validation" else "val", str(i))
                dist_path = os.path.join(class_path, image["filename"])
                export_image(image_path, dist_path, tuple(map(int, images_size.split("x"))))
        self.add_skipped_paths()


    def create_annotations(self):
        self.add_skipped_paths()
        classes_ids = self.get_classes_ids_numbers()
        for p1 in ["train", "val"]:
            for p2 in self.project_paths["dataset"][p1].keys():
                for filename, _ in self.project_paths["dataset"][p1][p2].items():
                    if _ is None:
                        image_data = self.get_image(filename=filename)
                        old_img_size = open_image(self.get_full_path("images", filename)).shape[:2][::-1]
                        new_img_size = open_image(self.get_full_path("dataset", p1, p2, filename)).shape[:2][::-1]
                        label_path = os.path.join(self.get_full_path("dataset", p1, p2, "labels"),
                                                  f"{filename.split('.')[0]}.txt")
                        with open(label_path, "w") as f:
                            for label in image_data["annotation"]:
                                obj_annotaion = ImageAnnotation.formate_bbox(tuple(label[1:]), old_img_size, new_img_size, "YOLO")
                                f.write(f"{classes_ids[label[0]]} {obj_annotaion}")


    def export(self) -> tuple[bool, str]:
        self.clear()
        try:
            classes_config = self.get_all_classes_conf(True)
            project_conf = self.get_configutation()
            self.create_paths(len(classes_config), project_conf["annotation"])
            self.create_yaml_config(classes_config)
            self.export_data(classes_config, project_conf["images_size"])
            if project_conf["annotation"]:
                self.create_annotations()
            return True, f"Датасет успешно экспортирован по пути: {self.get_full_path("dataset")}"
        except Exception as e:
            return False, f"Датасет не был создан. Ошибка: {e}"



@register_formatter("CSV")
class CSVdataset(BaseDataset):
    def create_paths(self, classes_len: int=0, annotation: bool=False):
        self.project_paths["dataset"] = {
            "train": {"images": {}},
            "val": {"images": {}},
            "train.csv": None,
            "val.csv": None
        }
        self.makedirs_ifnotexc()


    def export_data(self, classes_config: list=[], images_size: str="320x240"):
        if not classes_config:
            classes_config = self.get_all_classes_conf(True)
        resize_size = tuple(map(int, images_size.split("x")))
        for clas in classes_config:
            class_images = self.get_images(class_id=clas["id"])
            for image in class_images:
                image_path = self.get_full_path("images", image["filename"])
                split = "val" if image["type"] == "validation" else "train"
                dest_dir = self.get_full_path("dataset", split, "images")
                os.makedirs(dest_dir, exist_ok=True)
                dest_path = os.path.join(dest_dir, image["filename"])
                export_image(image_path, dest_path, resize_size)
        self.add_skipped_paths()


    def create_annotations(self):
        self.add_skipped_paths()

        project_conf = self.get_configutation()
        annotation_enabled = project_conf.get("annotation", False)
        resize_size = tuple(map(int, project_conf.get("images_size", "320x240").split("x")))
        classes_config = self.get_all_classes_conf(True)
        class_to_idx = {cls["id"]: idx for idx, cls in enumerate(classes_config)}

        for split in ["train", "val"]:
            images_dir = self.get_full_path("dataset", split, "images")
            if not images_dir or not os.path.exists(images_dir):
                continue
            csv_path = self.get_full_path("dataset", f"{split}.csv")
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                if annotation_enabled:
                    writer = csv.writer(csvfile)
                    writer.writerow(["filename", "class_id", "x_min", "y_min", "x_max", "y_max"])
                    for filename in os.listdir(images_dir):
                        if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                            continue
                        image_data = self.get_image(filename=filename)
                        if not image_data:
                            continue
                        original_path = self.get_full_path("images", filename)
                        original_img = open_image(original_path, None)
                        orig_h, orig_w = original_img.shape[:2]
                        new_w, new_h = resize_size
                        for ann in image_data["annotation"]:
                            class_id, x_min, y_min, x_max, y_max = ann
                            x_min_new = int(x_min * new_w / orig_w)
                            y_min_new = int(y_min * new_h / orig_h)
                            x_max_new = int(x_max * new_w / orig_w)
                            y_max_new = int(y_max * new_h / orig_h)
                            class_idx = class_to_idx.get(class_id, -1)
                            if class_idx == -1:
                                continue
                            writer.writerow([filename, class_idx, x_min_new, y_min_new, x_max_new, y_max_new])
                else:
                    writer = csv.writer(csvfile)
                    writer.writerow(["filename", "class_id"])
                    for filename in os.listdir(images_dir):
                        image_data = self.get_image(filename=filename)
                        class_idx = class_to_idx.get(image_data["class_id"], -1)
                        if class_idx == -1:
                            continue
                        writer.writerow([filename, class_idx])
        self.add_skipped_paths()


    def export(self) -> tuple[bool, str]:
        self.clear()
        try:
            classes_config = self.get_all_classes_conf(True)
            project_conf = self.get_configutation()
            self.create_paths()
            self.export_data(classes_config, project_conf["images_size"])
            self.create_annotations()
            return True, f"CSV датасет успешно экспортирован по пути: {self.get_full_path('dataset')}"
        except Exception as e:
            return False, f"Датасет не был создан. Ошибка: {e}"