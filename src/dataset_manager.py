import sqlite3
import filetype
import json
import uuid
import os



def get_image_type(image_bytes: bytes) -> str:
    kind = filetype.guess(image_bytes)
    if not kind or not kind.mime.startswith('image/'):
        return
    return kind.extension



class Dataset:
    def __init__(self, project_path: str):
        self.images_path = os.path.join(project_path, "images")
        os.makedirs(self.images_path, exist_ok=True)
        self.database_path = os.path.join(project_path, "project.sqlite")
        self.con = sqlite3.connect(self.database_path)
        self.con.row_factory = sqlite3.Row
        self.initDB()


    def initDB(self):
        cur = self.con.cursor()

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

        self.con.commit()


    def set_configutation(self, conf_data: dict):
        cur = self.con.cursor()
        cur.execute("DELETE FROM configuration;")
        for key, value in conf_data.items():
            cur.execute("INSERT INTO configuration(key, value)"+\
                        " VALUES(?, ?)", (key, str(value)))
        self.con.commit()

    def get_configutation(self) -> dict:
        cur = self.con.cursor()
        conf = dict(cur.execute("SELECT * FROM configuration").fetchall())
        for key, value in conf.items():
            if value.isdigit():
                conf[key] = int(value)
            elif value=="True" or value=="False":
                conf[key] = True if value=="True" else False
        return conf


    def add_or_upd_class_conf(self, class_name: str, enabled: bool = True,
                              subclasses: list = []) -> int:
        cur = self.con.cursor()
        result = cur.execute("SELECT id FROM classes_conf WHERE class_name = ?",
                             (class_name,)).fetchone()
        if result:
            class_id = result[0]
            cur.execute("UPDATE classes_conf SET enabled = ?, subclasses = ? "+\
                        "WHERE id = ?""", (enabled, json.dumps(subclasses, ensure_ascii=False), class_id))
        else:
            cur.execute("INSERT INTO classes_conf (class_name, enabled, subclasses) "+\
                        "VALUES (?, ?, ?)", (class_name, enabled, json.dumps(subclasses, ensure_ascii=False)))
            class_id = cur.lastrowid
        self.con.commit()
        return class_id

    def del_class_conf(self, class_id: int = None, class_name: str = None) -> bool:
        if not class_id and not class_name:
            return False
        cur = self.con.cursor()
        cur.execute("SELECT id FROM classes_conf WHERE id = ?", (class_id,))
        if not cur.fetchone():
            return False
        cur.execute("DELETE FROM classes_conf "+\
                    "WHERE id = ? OR class_name = ?", (class_id, class_name,))
        self.con.commit()
        return True

    def get_class_conf(self, class_id: int = None, class_name: str = None) -> dict:
        if not class_id and not class_name:
            return
        cur = self.con.cursor()
        result = dict(cur.execute("SELECT * FROM classes_conf WHERE id = ? OR class_name = ?",
                                  (class_id, class_name,)).fetchone())
        result["enabled"] = bool(result["enabled"])
        result["subclasses"] = json.loads(result["subclasses"])
        return result

    def get_all_classes_conf(self) -> list:
        cur = self.con.cursor()
        classes_ids = cur.execute("SELECT id FROM classes_conf").fetchall()
        result = []
        for class_id in classes_ids:
            result.append(self.get_class_conf(class_id[0]))
        return result


    def save_image(self, image_bytes: bytes, class_id: int,
                   type: str="default", annotation: list=[]) -> int:
        img_type = get_image_type(image_bytes)
        if img_type:
            filename = f"{uuid.uuid4().hex[:8]}.{img_type}"
            with open(os.path.join(self.images_path, filename), "wb") as f:
                f.write(image_bytes)
            cur = self.con.cursor()
            cur.execute("INSERT INTO dataset(filename, class_id, type, annotation) "+\
                        "VALUES(?, ?, ?, ?)", (filename, class_id, type, json.dumps(annotation)))
            self.con.commit()
            return cur.lastrowid

    def del_image(self, image_id: int=None, filename: str=None) -> bool:
        cur = self.con.cursor()
        cur.execute("DELETE FROM dataset "+\
                    "WHERE image_id = ? OR filename = ?", (image_id, filename,))
        self.con.commit()
        try:
            os.remove(filename)
            return True
        except:
            return False

    def get_image(self, image_id: int=None, filename: str=None) -> dict:
        cur = self.con.cursor()
        result = dict(cur.execute("SELECT * FROM dataset WHERE id = ? OR filename = ?",
                                  (image_id, filename,)).fetchone())
        result["annotation"] = json.loads(result["annotation"])
        return result

    def get_images(self, class_id: int=None) -> list:
        cur = self.con.cursor()
        ex, ex_atrbs = "SELECT id FROM dataset", ()
        if class_id:
            ex += " WHERE class_id = ?"
            ex_atrbs = (class_id,)
        result = []
        for class_id in cur.execute(ex, ex_atrbs).fetchall():
            result.append(self.get_image(class_id[0]))
        return result



if __name__ == "__main__": # Тест работы БД, вводим путь к проекту и проверяем вывод
    dataset = Dataset(input())
    dataset.set_configutation({
        "validation_data": False,
        "augmented_images": False,
        "annotation": True,
        "annotation_format": "YOLO",
        "images_per_class": 100
    })
    print("Configuration:", json.dumps(dataset.get_configutation(), indent=2, ensure_ascii=False), "\n")
    dataset.add_or_upd_class_conf("Гоночный транспорт")
    dataset.add_or_upd_class_conf("Гоночный транспорт", subclasses=[
        {"search_query": "спорткар maclaren",
         "example_image": "sportkar_maclaren.jpg"},
        {"search_query": "болид формула 1",
         "example_image": "bolid_formula_1.jpg"},
        {"search_query": "мотоцикл",
         "example_image": "mototsikl.jpg"}
    ])
    dataset.add_or_upd_class_conf("Городской транспорт", False, [
        {"search_query": "Автобус",
         "example_image": ""},
        {"search_query": "Троллейбус",
         "example_image": ""}
    ])
    print('Class "Городской транспорт" data:',
          dataset.get_class_conf(class_name="Городской транспорт"), "\n")
    print('All classes data:', dataset.get_all_classes_conf(), "\n")
    import requests
    image_request = requests.get("https://top-tuning.ru/w1200h627/upload/images/news/102829/2019-mclaren-600lt-limited-edition-1.jpg")
    image_id = dataset.save_image(image_request.content, dataset.get_class_conf(class_name="Гоночный транспорт")["id"])
    print(f'Image {image_id} from class "Гоночный транспорт" data:', dataset.get_image(image_id), "\n")
    print(f'Images from class "Гоночный транспорт" data:',
          dataset.get_images(dataset.get_class_conf(class_name="Гоночный транспорт")["id"]), "\n")
    print('All images data:', dataset.get_images())