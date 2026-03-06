import datetime
import getpass
import shutil
import yaml
import cv2
import os

from .project_manager import Project
from .photoshop import *


AVAILABLE_FORMATS = {}

def register_formatter(name):
    def decorator(cls):
        AVAILABLE_FORMATS[name] = cls
        return cls
    return decorator



def export_image(first_path: str, dist_path: str, resize_size: tuple=None):
    if os.path.exists(dist_path):
        os.remove(dist_path)
    image = open_image(first_path)
    if resize_size:
        image = resize_image(image, resize_size)
    _, encoded_image = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    with open(dist_path, 'wb') as f:
        f.write(encoded_image.tobytes())



@register_formatter("YOLO")
class YOLOdataset(Project):
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
            class_images = self.get_images(clas["id"])
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


    def put_data(self, dataset_path: str) -> tuple[bool, str]:
        try:
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



@register_formatter("CSV (нерабочий)")
class CSVdataset(Project):
    @classmethod
    def from_project(cls, project: Project):
        instance = cls.__new__(cls)
        instance.__dict__.update(project.__dict__)
        instance.add_skipped_paths()
        return instance

    def __init__(self, project_path: str):
        super().__init__(project_path)
        self.add_skipped_paths()
    

    def export(self):
        pass