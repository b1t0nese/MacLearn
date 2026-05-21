from pathlib import Path
import numpy as np
import shutil
import json
import os
import re
import sqlite3
import filetype
import uuid

from .photoshop import open_image



def get_image_type(image_bytes: bytes) -> str:
    kind = filetype.guess(image_bytes)
    if not kind or not kind.mime.startswith('image/'):
        return
    return kind.extension


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



class Dataset:
    def __init__(self, project_path: str):
        self.images_path = os.path.join(project_path, "images")
        os.makedirs(self.images_path, exist_ok=True)
        self.database_path = os.path.join(project_path, "project.sqlite")
        self.initDB()

    def get_connection(self):
        con = sqlite3.connect(self.database_path, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con


    def initDB(self):
        with self.get_connection() as con:
            cur = con.cursor()

            cur.execute("PRAGMA foreign_keys = ON;")

            cur.execute("""CREATE TABLE IF NOT EXISTS configuration (
                key TEXT PRIMARY KEY,
                value TEXT
            );""")

            cur.execute("""CREATE TABLE IF NOT EXISTS classes_conf (
                id INTEGER PRIMARY KEY,
                class_name TEXT NOT NULL UNIQUE,
                enabled BOOLEAN DEFAULT TRUE,
                subclasses TEXT DEFAULT "[]"
            );""")

            cur.execute("""CREATE TABLE IF NOT EXISTS dataset (
                id INTEGER PRIMARY KEY,
                filename TEXT NOT NULL,
                class_id INTEGER NOT NULL,
                type TEXT DEFAULT "DEFAULT",
                annotation TEXT DEFAULT "[]",
                parent_image_id INTEGER DEFAULT NULL,
                FOREIGN KEY (class_id) REFERENCES classes_conf(id)
                    ON DELETE CASCADE
                    ON UPDATE CASCADE,
                FOREIGN KEY (parent_image_id) REFERENCES dataset(id)
                    ON DELETE SET NULL
                    ON UPDATE CASCADE
            );""")

            con.commit()


    def set_configutation(self, conf_data: dict):
        with self.get_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM configuration;")
            for key, value in conf_data.items():
                cur.execute("INSERT INTO configuration(key, value)"+\
                            " VALUES(?, ?)", (key, str(value)))
            con.commit()

    def get_configutation(self) -> dict:
        with self.get_connection() as con:
            cur = con.cursor()
            conf = dict(cur.execute("SELECT * FROM configuration").fetchall())
            for key, value in conf.items():
                if value.isdigit():
                    conf[key] = int(value)
                elif value=="True" or value=="False":
                    conf[key] = True if value=="True" else False
            return conf


    def add_or_upd_class_conf(self, class_name: str, class_id: int=None,
                              enabled: bool = True, subclasses: list = []):
        with self.get_connection() as con:
            cur = con.cursor()
            result = cur.execute("SELECT id FROM classes_conf WHERE class_name = ?", (
                class_name,)).fetchone() if not class_id else [class_id]
            if result:
                cur.execute("UPDATE classes_conf SET class_name = ?, enabled = ?, subclasses = ? "+\
                            "WHERE id = ?""", (class_name, enabled, json.dumps(subclasses, ensure_ascii=False), result[0]))
            else:
                cur.execute("INSERT INTO classes_conf (class_name, enabled, subclasses) "+\
                            "VALUES (?, ?, ?)", (class_name, enabled, json.dumps(subclasses, ensure_ascii=False)))
            con.commit()

    def del_class_conf(self, class_id: int = None, class_name: str = None) -> bool:
        with self.get_connection() as con:
            if not class_id and not class_name:
                return False
            cur = con.cursor()
            cur.execute("SELECT id FROM classes_conf "+\
                        "WHERE id = ? OR class_name = ?", (class_id, class_name,))
            if not cur.fetchone():
                return False
            cur.execute("DELETE FROM classes_conf "+\
                        "WHERE id = ? OR class_name = ?", (class_id, class_name,))
            con.commit()
            return True

    def get_class_conf(self, class_id: int = None, class_name: str = None) -> dict:
        with self.get_connection() as con:
            if not class_id and not class_name:
                return
            cur = con.cursor()
            result = dict(cur.execute("SELECT * FROM classes_conf WHERE id = ? OR class_name = ?",
                                    (class_id, class_name,)).fetchone())
            if result:
                result["enabled"] = bool(result["enabled"])
                result["subclasses"] = json.loads(result["subclasses"])
                return result

    def get_all_classes_conf(self, enabled: bool=None) -> list[dict]:
        with self.get_connection() as con:
            cur = con.cursor()
            classes_ids = cur.execute(f"SELECT id FROM classes_conf{\
                " WHERE enabled=?" if enabled is not None else ""} ORDER BY id",
                (enabled,) if enabled is not None else ()).fetchall()
            result = []
            for class_id in classes_ids:
                class_data = self.get_class_conf(class_id[0])
                class_data["class_id"] = class_id[0]
                result.append(class_data)
            return result

    def get_classes_ids_numbers(self) -> dict[int, int]:
        classes_conf = self.get_all_classes_conf()
        classes_ids = sorted(map(lambda x: x["class_id"], classes_conf))
        return dict([(x, i) for i, x in enumerate(classes_ids)])


    def save_image(self, image_bytes: bytes, class_id: int, image_type: str="default",
                   annotation: list=[], parent_image_id: int=None) -> int:
        with self.get_connection() as con:
            img_exp = get_image_type(image_bytes)
            if img_exp:
                filename = ""
                while not (filename and not self.get_image(filename=filename)):
                    filename = f"{uuid.uuid4().hex[:8]}.{img_exp}"
                with open(os.path.join(self.images_path, filename), "wb") as f:
                    f.write(image_bytes)
                cur = con.cursor()
                cur.execute("INSERT INTO dataset(filename, class_id, type, annotation, parent_image_id) "+\
                            "VALUES(?, ?, ?, ?, ?)", (filename, class_id, image_type, json.dumps(annotation), parent_image_id))
                con.commit()
                return int(cur.lastrowid)

    def change_image(self, image_id: int=None, filename: str=None,
                     class_id: int=None, image_type: str=None, annotation: list=None) -> dict:
        with self.get_connection() as con:
            cur = con.cursor()
            if filename and not image_id:
                image_id = cur.execute(
                    "SELECT id FROM dataset WHERE filename = ?", (filename,)).fetchone()[0]
            elif not filename and not image_id:
                return False
            sql, params = "UPDATE dataset SET", []
            if class_id:
                sql += " class_id=?,"; params.append(class_id)
            if image_type:
                sql += " type=?,"; params.append(image_type)
            if annotation:
                sql += " annotation=?,"
                params.append(json.dumps(annotation, ensure_ascii=False))
            sql = sql.rstrip(",")+" WHERE id=?"
            cur.execute(sql, tuple(params+[image_id]))
            return dict(cur.execute("SELECT * FROM dataset WHERE id = ?", (image_id,)).fetchone())

    def del_image(self, image_id: int=None, filename: str=None) -> bool:
        with self.get_connection() as con:
            cur = con.cursor()
            if not filename and image_id:
                filename = cur.execute(
                    "SELECT filename FROM dataset WHERE id = ?", (image_id,)).fetchone()[0]
            else:
                return False
            cur.execute("DELETE FROM dataset "+\
                        "WHERE id = ? OR filename = ?", (image_id, filename,))
            con.commit()
            try:
                os.remove(os.path.join(self.images_path, filename))
                return True
            except:
                return False

    def get_image(self, image_id: int=None, filename: str=None) -> dict | bool:
        with self.get_connection() as con:
            cur = con.cursor()
            result = cur.execute("SELECT * FROM dataset WHERE id = ? OR filename = ?",
                                 (image_id, filename,)).fetchone()
            if result:
                result = dict(result)
                result["annotation"] = json.loads(result["annotation"])
                return result

    def get_images(self, **kwargs) -> list[dict]:
        with self.get_connection() as con:
            cur = con.cursor()
            ex, ex_atrbs = "SELECT id FROM dataset", []
            if kwargs:
                ex += " WHERE"
                for key, item in kwargs.items():
                    ex += f"{" AND" if ex_atrbs else ""} {key} = ?"
                    ex_atrbs.append(item)
            result = []
            for class_id in cur.execute(ex, tuple(ex_atrbs)).fetchall():
                result.append(self.get_image(class_id[0]))
            return result



class Project(Dataset):
    def __init__(self, path: str):
        super().__init__(path)
        self.project_path = path
        self.project_paths = {
            "example_images": {},
            "images": {},
            "project.sqlite": None
        }
        self.makedirs_ifnotexc()
        self.add_skipped_paths()
        if not self.get_configutation():
            self.save({
                "validation_data": True,
                "augmentation_count": 0,
                "annotation": True,
                "dataset_format": "YOLO",
                "images_per_class": 100,
                "images_size": "320x240"
            })


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

    def add_skipped_paths(self):
        base = Path(self.project_path)
        def scan_all_paths(current_path, structure_node):
            if not current_path.exists() or not current_path.is_dir():
                return
            for item in current_path.iterdir():
                if item.name not in structure_node:
                    if item.is_dir():
                        structure_node[item.name] = {}
                        scan_all_paths(item, structure_node[item.name])
                    else:
                        structure_node[item.name] = None
                else:
                    if isinstance(structure_node[item.name], dict) and item.is_dir():
                        scan_all_paths(item, structure_node[item.name])
        scan_all_paths(base, self.project_paths)

    def get_full_path(self, *path_parts: str) -> str:
        self.add_skipped_paths()
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
        need_paths = ["example_images", "images", "project.sqlite"]
        have_paths = map(lambda p: os.path.exists(os.path.join(project_path, p)), need_paths)
        return all(have_paths)


    def save(self, configuration: dict, classes_conf: list=[]):
        for i, class_data in enumerate(classes_conf):
            for j, subclass_data in enumerate(class_data["subclasses"]):
                if "/" in subclass_data["example_image"]:
                    classes_conf[i]["subclasses"][j]["example_image"] = self.add_subclass_example_image(subclass_data)
        self.add_skipped_paths()
        for file in self.project_paths["example_images"].keys():
            if file not in self.find_all_values_by_key(classes_conf, "example_image"):
                os.remove(self.get_full_path("example_images", file))
        self.add_skipped_paths()
        self.set_configutation(configuration)
        for class_data in self.get_all_classes_conf():
            if class_data["id"] is not None and class_data["id"] not in [clasdat["class_id"] for clasdat in classes_conf]:
                self.del_class_conf(class_data["id"])
                for image in self.get_images(class_id=class_data["id"]):
                    self.del_image(image["id"])
        for class_data in classes_conf:
            self.add_or_upd_class_conf(**class_data)

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
            return True, f"Проект успешно сохранён по пути: {to_path}"
        except Exception as e:
            return False, f"Проект не был сохранён по новому пути. Ошибка: {e}"

    def get_project_conf(self) -> dict:
        return {
            "configuration": self.get_configutation(),
            "classes": self.get_all_classes_conf()
        }


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

    def find_all_values_by_key(self, data: list, search_key: str) -> set:
        results = set()
        def _traverse(obj):
            if isinstance(obj, dict):
                if search_key in obj:
                    value = obj[search_key]
                    results.add(value)
                for value in obj.values():
                    _traverse(value)
            elif isinstance(obj, (list, tuple, set)):
                for item in obj:
                    _traverse(item)
        _traverse(data)
        return results



def get_dataset_statistics(project: Project) -> dict:
    stats = {
        "Общая информация": {},
        "Изображения": {},
        "Аннотации": {},
        "Классы": {},
        "Качество и свойства": {},
        "Конфигурация проекта": {}
    }
    project_conf = project.get_project_conf()
    configuration = project_conf["configuration"]
    classes = project_conf["classes"]
    all_images = project.get_images()
    total_images = len(all_images)
    stats["Общая информация"] = {
        "Путь проекта": project.project_path,
        "Версия структуры": "1.0",
        "Наличие example_images": bool(project.get_full_path("example_images")),
        "Размер БД (МБ)": round(os.path.getsize(project.database_path) / (1024 * 1024), 2) if os.path.exists(project.database_path) else 0
    }
    total_size_bytes = 0
    resolutions = []
    formats = set()

    for img in all_images:
        img_path = os.path.join(project.images_path, img["filename"])
        if os.path.exists(img_path):
            size = os.path.getsize(img_path)
            total_size_bytes += size
            try:
                mat_image = open_image(img_path)
                resolutions.append(mat_image.shape[:2][::-1])
                formats.add(mat_image.format)
            except:
                ext = os.path.splitext(img["filename"])[1].lower()
                formats.add(ext)

    avg_width = sum(r[0] for r in resolutions) // len(resolutions) if resolutions else 0
    avg_height = sum(r[1] for r in resolutions) // len(resolutions) if resolutions else 0
    stats["Изображения"] = {
        "Всего изображений": total_images,
        "Общий размер (МБ)": round(total_size_bytes / (1024 * 1024), 2),
        "Средний размер файла (КБ)": round((total_size_bytes / total_images) / 1024, 2) if total_images > 0 else 0,
        "Форматы изображений": list(formats) if formats else ["не определено"],
        "Среднее разрешение": f"{avg_width}x{avg_height}" if resolutions else "не определено",
        "Пустые изображения (без аннотаций)": len([img for img in all_images if not img["annotation"] or img["annotation"] == "[]"]),
        "Типы изображений": list(set(img["type"] for img in all_images))
    }
    total_annotations = 0
    annotations_per_image = []
    all_annotations_raw = []
    
    for img in all_images:
        annotation = img["annotation"]
        if annotation and isinstance(annotation, (list, dict)):
            if isinstance(annotation, list):
                ann_count = len(annotation)
            elif isinstance(annotation, dict):
                ann_count = len(annotation.get("annotations", annotation.get("boxes", [])))
            else:
                ann_count = 0
            total_annotations += ann_count
            annotations_per_image.append(ann_count)
            all_annotations_raw.append(annotation)
    stats["Аннотации"] = {
        "Всего аннотаций": total_annotations,
        "Среднее аннотаций на изображение": round(total_annotations / total_images, 2) if total_images > 0 else 0,
        "Максимум аннотаций на изображение": max(annotations_per_image) if annotations_per_image else 0,
        "Минимум аннотаций на изображение": min(annotations_per_image) if annotations_per_image else 0,
        "Медиана аннотаций на изображение": sorted(annotations_per_image)[len(annotations_per_image)//2] if annotations_per_image else 0,
        "Изображения с аннотациями": len([c for c in annotations_per_image if c > 0]),
        "Изображения без аннотаций": len([c for c in annotations_per_image if c == 0])
    }

    class_stats = {}
    for cls in classes:
        class_id = cls["class_id"]
        class_name = cls["class_name"]
        images_in_class = project.get_images(class_id=class_id)
        class_stats[class_name] = {
            "id": class_id,
            "включен": cls["enabled"],
            "количество изображений": len(images_in_class),
            "количество подклассов": len(cls.get("subclasses", [])),
            "подклассы": [sc.get("search_query", sc.get("class_name", "unnamed")) for sc in cls.get("subclasses", [])]
        }

    class_counts = [stats["количество изображений"] for stats in class_stats.values()]
    stats["Классы"] = {
        "Всего классов": len(classes),
        "Всего подклассов": sum(len(cls.get("subclasses", [])) for cls in classes),
        "Включенных классов": len([c for c in class_stats.values() if c["включен"]]),
        "Детали по классам": class_stats,
        "Максимум изображений в классе": max(class_counts) if class_counts else 0,
        "Минимум изображений в классе": min(class_counts) if class_counts else 0,
        "Среднее изображений на класс": round(sum(class_counts) / len(class_counts), 2) if class_counts else 0,
        "Баланс классов (коэффициент вариации)": round((max(class_counts) - min(class_counts)) / (sum(class_counts) / len(class_counts)), 2) if class_counts and sum(class_counts) > 0 else 0
    }

    example_images_path = project.get_full_path("example_images")
    example_images = []
    if example_images_path and os.path.exists(example_images_path):
        example_images = [f for f in os.listdir(example_images_path) if os.path.isfile(os.path.join(example_images_path, f))]
    stats["Качество и свойства"] = {
        "Примерных изображений (подклассов)": len(example_images),
        "Есть родительские изображения (производные)": len([img for img in all_images if img.get("parent_image_id")]),
        "Производные изображения (увеличение)": len([img for img in all_images if img.get("type") and img["type"] != "DEFAULT"]),
        "Соотношение типов изображений": dict(zip(*np.unique([img["type"] for img in all_images], return_counts=True))) if all_images else {},
        "Целостность данных": "OK" if all(os.path.exists(os.path.join(project.images_path, img["filename"])) for img in all_images) else "Некоторые файлы отсутствуют"
    }
    stats["Конфигурация проекта"] = {
        "Формат датасета": configuration.get("dataset_format", "не задан"),
        "Увеличение данных (аугментация)": f"{configuration.get('augmentation_count', 0)}x",
        "Валидация данных": configuration.get("validation_data", False),
        "Аннотации включены": configuration.get("annotation", False),
        "Изображений на класс": configuration.get("images_per_class", 0),
        "Размер изображений": configuration.get("images_size", "не задан")
    }
    
    return stats