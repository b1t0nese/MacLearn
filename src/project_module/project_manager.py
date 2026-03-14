from pathlib import Path
import shutil
import json
import os
import re
import sqlite3
import filetype
import uuid



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

            cur.execute("""CREATE TABLE IF NOT EXISTS configuration (
                key TEXT PRIMARY KEY,
                value TEXT
            );""")

            cur.execute("PRAGMA foreign_keys = ON;")

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
                FOREIGN KEY (class_id) REFERENCES classes_conf(id),
                FOREIGN KEY (class_id) REFERENCES classes_conf(id)
                    ON DELETE CASCADE
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


    def add_or_upd_class_conf(self, class_id: int=None, class_name: str=None, enabled: bool = True,
                              subclasses: list = []) -> int | bool:
        with self.get_connection() as con:
            cur = con.cursor()
            if not class_id:
                class_id, class_name = cur.execute("SELECT id, class_name FROM classes_conf WHERE class_name = ?",
                                                   (class_name,)).fetchone()
            elif not class_name:
                class_id, class_name = cur.execute("SELECT id, class_name FROM classes_conf WHERE class_name = ?",
                                                   (class_name,)).fetchone()
            if class_id:
                cur.execute("UPDATE classes_conf SET class_name = ?, enabled = ?, subclasses = ? "+\
                            "WHERE id = ?""", (class_name, enabled, json.dumps(subclasses, ensure_ascii=False), class_id))
            elif class_name:
                cur.execute("INSERT INTO classes_conf (class_name, enabled, subclasses) "+\
                            "VALUES (?, ?, ?)", (class_name, enabled, json.dumps(subclasses, ensure_ascii=False)))
                class_id = cur.lastrowid
            else:
                return
            con.commit()
            return class_id

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
                " WHERE enabled=?" if enabled is not None else ""}",
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


    def save_image(self, image_bytes: bytes, class_id: int,
                   image_type: str="default", annotation: list=[]) -> int:
        with self.get_connection() as con:
            img_exp = get_image_type(image_bytes)
            if img_exp:
                filename = f"{uuid.uuid4().hex[:8]}.{img_exp}"
                with open(os.path.join(self.images_path, filename), "wb") as f:
                    f.write(image_bytes)
                cur = con.cursor()
                cur.execute("INSERT INTO dataset(filename, class_id, type, annotation) "+\
                            "VALUES(?, ?, ?, ?)", (filename, class_id, image_type, json.dumps(annotation)))
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

    def get_image(self, image_id: int=None, filename: str=None) -> dict:
        with self.get_connection() as con:
            cur = con.cursor()
            result = dict(cur.execute("SELECT * FROM dataset WHERE id = ? OR filename = ?",
                                      (image_id, filename,)).fetchone())
            result["annotation"] = json.loads(result["annotation"])
            return result

    def get_images(self, class_id: int=None, images_type: str=None) -> list[dict]:
        with self.get_connection() as con:
            cur = con.cursor()
            ex, ex_atrbs = "SELECT id FROM dataset", []
            if class_id or images_type:
                ex += " WHERE"
                if class_id:
                    ex += " class_id = ?"
                    ex_atrbs.append(class_id)
                if images_type:
                    ex += f"{" AND" if class_id else ""} type = ?"
                    ex_atrbs.append(images_type)
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
                "augmentation": False,
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
            if class_data["id"] not in [clasdat["class_id"] for clasdat in classes_conf]:
                self.del_class_conf(class_data["id"])
                for image in self.get_images(class_data["id"]):
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