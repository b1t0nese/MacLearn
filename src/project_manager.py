from pathlib import Path
import shutil
import json
import os
import re



def to_snake_case(text: str) -> str:
    translit_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        ' ': '_'
    }
    text = text
    result = []
    for char in text.lower():
        if char in translit_dict:
            result.append(translit_dict[char])
        elif char.isalnum():
            result.append(char)
        else:
            result.append('_')
    snake_text = ''.join(result)
    snake_text = re.sub(r'_+', '_', snake_text)
    return snake_text.strip('_')



class Project:
    def __init__(self, path: str):
        self.project_path = path
        self.project_paths = {
            "example_images": {},
            "images": {},
            "project.conf": None
        }
        self.makedirs_ifnotexc()
        self.add_skipped_paths()
        self.load()


    def makedirs_ifnotexc(self):
        base = Path(self.project_path)
        def process_structure(current_path, structure):
            for key, value in structure.items():
                item_path = current_path / key
                if isinstance(value, dict):
                    item_path.mkdir(parents=True, exist_ok=True)
                    process_structure(item_path, value)
                elif value is None:
                    item_path.touch(exist_ok=True)
        process_structure(base, self.project_paths)
        return True

    def add_skipped_paths(self):
        base = Path(self.project_path)
        def scan_and_add_paths(current_path, structure_node):
            if current_path.exists() and current_path.is_dir():
                for item in current_path.iterdir():
                    if item.name not in structure_node:
                        if item.is_dir():
                            structure_node[item.name] = {}
                            scan_and_add_paths(item, structure_node[item.name])
                        elif item.is_file():
                            structure_node[item.name] = None
        for key, value in self.project_paths.items():
            if isinstance(value, dict):
                folder_path = base / key
                scan_and_add_paths(folder_path, self.project_paths[key])
            elif value is None:
                file_path = base / key
                if file_path.exists() and file_path.name not in self.project_paths:
                    self.project_paths[file_path.name] = None

    def get_full_path(self, *path_parts: str) -> str:
        current_level = self.project_paths
        full_path = Path(self.project_path)
        for part in path_parts:
            if part in current_level:
                full_path = full_path / part
                if isinstance(current_level[part], dict):
                    current_level = current_level[part]
                else: break
            else: return None
        return str(full_path).replace('\\', '/')


    def path_is_project(project_path: str) -> bool:
        return os.path.exists(os.path.join(project_path, "project.conf"))

    def load(self) -> bool:
        try:
            with open(self.get_full_path("project.conf"), "r", encoding="utf-8") as f:
                self.project = json.load(f)
        except:
            self.project = {
                "classes": [],
                "dataset_settings": {
                    "validation_data": True,
                    "augmented_images": False,
                    "annotation": True,
                    "annotation_format": "YOLO",
                    "images_per_class": 100
                }
            }
            self.save(self.project)

    def save(self, data: dict) -> bool:
        for i, class_data in enumerate(data["classes"]):
            for j, subclass_data in enumerate(class_data["subclasses"]):
                if "/" in subclass_data["example_image"]:
                    data["classes"][i]["subclasses"][j]["example_image"] = self.add_subclass_example_image(subclass_data)
        self.add_skipped_paths()
        for file in self.project_paths["example_images"].keys():
            if file not in self.get_all_example_images(data):
                os.remove(self.get_full_path("example_images", file))
        self.add_skipped_paths()
        self.project = data
        with open(self.get_full_path("project.conf"), "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False))

    def save_as(self, to_path: str) -> tuple:
        try:
            os.makedirs(to_path, exist_ok=True)
            for item in os.listdir(self.project_path):
                source_item = os.path.join(self.project_path, item)
                dest_item = os.path.join(to_path, item)
                if os.path.isdir(source_item):
                    shutil.copytree(source_item, dest_item, dirs_exist_ok=True)
                else:
                    shutil.copy2(source_item, dest_item)
            return True, f"Датасет успешно сохранён по пути: {to_path}"
        except Exception as e:
            return False, f"Проект не был сохранён по новому пути. Ошибка: {e}"


    def add_subclass_example_image(self, subclass_data: dict) -> str:
        try:
            img_path = subclass_data["example_image"]
            new_path = self.get_full_path("example_images")
            new_filename = to_snake_case(subclass_data["search_query"])+\
                "."+os.path.basename(img_path).split(".")[-1]
            new_path = os.path.join(new_path, new_filename)
            shutil.copy(img_path, new_path)
            return new_filename
        except shutil.SameFileError:
            return os.path.basename(subclass_data["example_image"])

    def get_all_example_images(self, data) -> set:
        example_images = set()
        def find_example_images(obj):
            if isinstance(obj, dict):
                if "example_image" in obj and isinstance(obj["example_image"], str):
                    example_images.add(obj["example_image"])
                for value in obj.values():
                    find_example_images(value)
            elif isinstance(obj, list):
                for item in obj:
                    find_example_images(item)
        find_example_images(data)
        return example_images


    def generate_yaml_config(self) -> bool:
        """Генерирует dataset.yaml для YOLO"""
        pass

    def export_dataset(self, export_format: str = "YOLO") -> bool:
        """Экспортирует датасет в указанном формате"""
        pass