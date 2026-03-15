import cv2
from cv2.typing import MatLike
import numpy as np
import rembg



def open_image(file_path: str, color=cv2.COLOR_BGR2RGB) -> MatLike:
    with open(file_path, 'rb') as f:
        img_array = np.frombuffer(f.read(), dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return cv2.cvtColor(image, color)


def resize_image(img: MatLike, target_size: tuple=(300, 300)) -> MatLike:
    height, width = img.shape[:2]
    scale = min(target_size[0] / width, target_size[1] / height)
    new_width, new_height = int(width * scale), int(height * scale)
    resized_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
    return resized_img


def visualize_bbox(img: MatLike, bboxes: list[list[int]], classes_colors: list[tuple[int]] = None) -> MatLike:
    result = img.copy()
    if classes_colors is None:
        unique_classes = sorted(set(bbox[0] for bbox in bboxes))
        classes_colors = {}
        for i, class_id in enumerate(unique_classes):
            color = cv2.cvtColor(np.uint8([[[(i*30)%180, 255, 255]]]), cv2.COLOR_HSV2BGR)[0][0]
            classes_colors[class_id] = (int(color[0]), int(color[1]), int(color[2]))
    else:
        classes_colors_dict = {}
        for i, class_id in enumerate(sorted(set(bbox[0] for bbox in bboxes))):
            if i<len(classes_colors):
                classes_colors_dict[class_id] = classes_colors[i]
            else:
                classes_colors_dict[class_id] = classes_colors[i % len(classes_colors)]
        classes_colors = classes_colors_dict
    for bbox in bboxes:
        class_id, x, y, w, h = bbox
        cv2.rectangle(result, (x, y), (x + w, y + h), classes_colors[class_id], 2)
        label_size, _ = cv2.getTextSize(str(class_id), cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
        cv2.rectangle(result, (x, y - label_size[1] - 5), (x + label_size[0] + 5, y),  classes_colors[class_id], -1)
        cv2.putText(result, str(class_id), (x + 2, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 1, cv2.LINE_AA)
    return result



class ImageAnnotation:
    def formate_bbox(bbox: tuple[int], img_size: tuple[int]=None,
                     new_img_size: tuple[int]=None, ann_type: str=None) -> str:
        """Formate bbox for new image or other annotation type

        :param bbox: bounding box data of the type (x, y, w, h)
        :type bbox: tuple[int]
        :param img_size: Optionally: (w, h) of the image in which the bbox was received, it is necessary for type="YOLO" or when resizing the image
        :type img_size: tuple[int] = None
        :param new_img_size: Optionally: (w, h) of the image to create a new annotation for
        :type new_img_size: tuple[int] = None
        :param ann_type: the name of the annotation type used, available: "YOLO", "COCO", "PASCAL_VOC", None (default bbox)
        :type ann_type: str = None
        :return: formatted annotation as string
        """ # это всего лишь тест аннотаций кода, которые я буду делать в будущем для волонтёров-разработчиков
        x, y, w, h = bbox
        target_size = new_img_size if new_img_size else img_size

        if img_size and new_img_size:
            scale_x, scale_y = new_img_size[0] / img_size[0], new_img_size[1] / img_size[1]
            x_scaled, y_scaled = x * scale_x, y * scale_y
            w_scaled, h_scaled = w * scale_x, h * scale_y
        else:
            x_scaled, y_scaled, w_scaled, h_scaled = x, y, w, h
        x_int, y_int = int(round(x_scaled)), int(round(y_scaled))
        w_int, h_int = int(round(w_scaled)), int(round(h_scaled))

        if ann_type == "YOLO" and target_size:
            x_center = (x_scaled + w_scaled / 2) / target_size[0]
            y_center = (y_scaled + h_scaled / 2) / target_size[1]
            width_norm, height_norm = w_scaled / target_size[0], h_scaled / target_size[1]
            return f"{x_center:.6f} {y_center:.6f} {width_norm:.6f} {height_norm:.6f}"
        elif ann_type == "COCO":
            return f"[{x_int}, {y_int}, {w_int}, {h_int}]"
        elif ann_type == "PASCAL_VOC":
            return f"<xmin>{x_int}</xmin><ymin>{y_int}</ymin><xmax>{x_int + w_int}</xmax><ymax>{y_int + h_int}</ymax>"
        else:
            return f"{x_int} {y_int} {w_int} {h_int}"


    def __init__(self, contour: MatLike, img_size: tuple[int]):
        self.contour: MatLike = contour
        self.img_size = img_size
        self.hull: MatLike = None
        self.bbox: tuple[int] = ()
        self.bbox_center: tuple[int] = ()
        self.bbox_yolo = ""
        self.bbox_coco = ""
        self.bbox_pascal_voc = ""


    def calculate_rect(self):
        epsilon = 0.005 * cv2.arcLength(self.contour, True)
        approx = cv2.approxPolyDP(self.contour, epsilon, True)
        self.hull = cv2.convexHull(approx)


    def calc(self):
        if self.hull is None:
            self.calculate_rect()
        bbox = cv2.boundingRect(self.hull)

        self.bbox = bbox
        self.bbox_center = (bbox[0] + bbox[2]//2, bbox[1] + bbox[3]//2)
        self.bbox_area = int(cv2.contourArea(self.contour))
        self.bbox_yolo = ImageAnnotation.formate_bbox(bbox, self.img_size, ann_type="YOLO")
        self.bbox_coco = ImageAnnotation.formate_bbox(bbox, ann_type="COCO")
        self.bbox_pascal_voc = ImageAnnotation.formate_bbox(bbox, ann_type="PASCAL_VOC")


    def get(self):
        self.calculate_rect()
        self.calc()
        return {
            "bbox": self.bbox,
            "center": self.bbox_center,
            "area": self.bbox_area,
            "yolo": self.bbox_yolo,
            "coco": self.bbox_coco,
            "pascal_voc": self.bbox_pascal_voc
        }


    def put_contour_on_image(self, array_image: MatLike, contour: tuple[int]=(),
                             hull_contour: tuple[int]=(), rectangle: tuple[int]=(0, 0, 255)) -> MatLike:
        x, y, w, h = cv2.boundingRect(self.hull)

        array_image_new = array_image.copy()
        if contour:
            cv2.drawContours(array_image_new, [self.contour], -1, contour, 2)
        if hull_contour:
            cv2.drawContours(array_image_new, [self.hull], -1, hull_contour, 2)
        if rectangle:
            cv2.rectangle(array_image_new, (x, y), (x + w, y + h), rectangle, 2)
        
        return array_image_new



class ImageAnnotationDetector:
    def __init__(self, image: MatLike, max_objects: int=1, min_object_area: int=5000):
        self.image = image

        self.contours = None
        self.needed_contours = None
        self.annotations: list[ImageAnnotation] = []

        self.max_objects = max_objects
        self.min_object_area = min_object_area


    def remove_bg(self):
        self.image = rembg.remove(self.image)


    def detect_contours(self):
        self.blurred = cv2.GaussianBlur(self.image, (11, 11), 0)
        self.gray = cv2.cvtColor(self.blurred, cv2.COLOR_BGR2GRAY)
        self.edges = cv2.Canny(self.gray, 20, 80)
        kernel = np.ones((7, 7), np.uint8)
        closed = cv2.morphologyEx(self.edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        dilated = cv2.dilate(closed, kernel, iterations=3)
        filled = cv2.morphologyEx(
            dilated, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)), iterations=2)
        self.contours, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.needed_contours = self.contours


    def smooth_contours(self):
        mask = np.zeros_like(self.gray)
        for contour in self.contours:
            cv2.drawContours(mask, [contour], -1, 255, -1)
        mask = cv2.GaussianBlur(mask, (21, 21), 0)
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
        self.contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.needed_contours = self.contours


    def filter_contours_to_needed(self, max_contours: int=None, min_area: int=None):
        max_contours = max_contours if max_contours else self.max_objects
        min_area = min_area if min_area else self.min_object_area
        contours = sorted(self.contours, key=cv2.contourArea, reverse=True)[:max_contours]
        self.needed_contours = [c for c in contours if cv2.contourArea(c) > min_area]


    def calculate_bboxes_data(self) -> list[dict]:
        if self.needed_contours:
            self.annotations, annotations_data = [], []
            for contour in self.needed_contours:
                annotation = ImageAnnotation(contour, self.image.shape[:2][::-1])
                data = annotation.get()
                annotations_data.append(data)
                self.annotations.append(annotation)
            return annotations_data


    def put_contours_on_image(self, array_image: MatLike, contours: tuple[int]=(),
                              hull_contours: tuple[int]=(), rectangles: tuple[int]=(0, 0, 255)) -> MatLike:
        array_image_new = array_image.copy()
        for annotation in self.annotations:
            array_image_new = annotation.put_contour_on_image(array_image_new, contours, hull_contours, rectangles)
        return array_image_new