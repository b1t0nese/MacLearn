import cv2
import os
from cv2.typing import MatLike
import albumentations as AX
import numpy as np
from PIL import Image
from sam3_studio_lib import AnnotationConfig, ClassConfig, Sam3Annotator
from pcfuncs import get_appdata_dir



def open_image(file_path: str, color=cv2.COLOR_BGR2RGB) -> MatLike:
    with open(file_path, 'rb') as f:
        img_array = np.frombuffer(f.read(), dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return image if color is None else cv2.cvtColor(image, color)


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



def generate_augmentations(image_path, bboxes_xywh, category_ids, n=5):
    image = cv2.imread(image_path)
    if image is None:
        return []
    image_height, image_width = image.shape[:2]
    valid_bboxes, valid_category_ids = [], []
    for bbox, category_id in zip(bboxes_xywh, category_ids):
        x, y, width, height = map(float, bbox)
        x1 = max(0.0, min(x, image_width))
        y1 = max(0.0, min(y, image_height))
        x2 = max(0.0, min(x + width, image_width))
        y2 = max(0.0, min(y + height, image_height))
        if x2 > x1 and y2 > y1:
            valid_bboxes.append([x1, y1, x2 - x1, y2 - y1])
            valid_category_ids.append(category_id)
    if not valid_bboxes:
        return []
    results = []
    for i in range(n):
        h, w = image.shape[:2]

        pipeline = AX.Compose([
            AX.AtLeastOneBBoxRandomCrop(
                height=np.random.randint(h//2, h),
                width=np.random.randint(w//2, w), p=0.5),
            AX.HorizontalFlip(p=0.3),
            AX.VerticalFlip(p=0.2),
            AX.RandomRotate90(p=0.3),
            AX.ShiftScaleRotate(
                shift_limit=np.random.uniform(0, 0.2),
                scale_limit=np.random.uniform(0, 0.3),
                rotate_limit=np.random.randint(10, 45), p=0.4),
            AX.OneOf([
                AX.RandomBrightnessContrast(
                    brightness_limit=np.random.uniform(0.1, 0.3),
                    contrast_limit=np.random.uniform(0.1, 0.3), p=1.0),
                AX.HueSaturationValue(
                    hue_shift_limit=np.random.randint(10, 30),
                    sat_shift_limit=np.random.randint(10, 40),
                    val_shift_limit=np.random.randint(10, 30), p=1.0),
                AX.ColorJitter(
                    brightness=np.random.uniform(0.1, 0.3),
                    contrast=np.random.uniform(0.1, 0.3),
                    saturation=np.random.uniform(0.1, 0.3),
                    hue=np.random.uniform(0.05, 0.15), p=1.0),
            ], p=0.5),
            AX.OneOf([
                AX.GaussNoise(p=1.0),
                AX.ISONoise(
                    color_shift=(0.01, 0.05),
                    intensity=(0.1, 0.5),
                    p=1.0),
                AX.MultiplicativeNoise(
                    multiplier=(0.9, 1.1), p=1.0),
            ], p=0.3),
            AX.OneOf([
                AX.Blur(blur_limit=(3, 7), p=1.0),
                AX.GaussianBlur(blur_limit=(3, 7), p=1.0),
                AX.MedianBlur(blur_limit=7, p=1.0),
            ], p=0.2),
        ], bbox_params=AX.BboxParams(
            coord_format='coco', label_fields=['category_ids'],
            min_visibility=0.2, clip_after_transform=True, min_area=50))

        augmented = pipeline(image=image, bboxes=valid_bboxes, category_ids=valid_category_ids)
        results.append({
            "image": augmented['image'],
            "bboxes": augmented['bboxes'],
            "category_ids": augmented['category_ids']
        })
    return results



class ImageAnnotation:
    @staticmethod
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
    def __init__(self, image: MatLike, classes_conf: list[dict],
                 configuration: dict = None, annotator: Sam3Annotator = None):
        self.image = image
        self.classes_conf = classes_conf
        self.configuration = configuration or {}
        self.class_ids = [
            class_data.get("id", class_data.get("class_id"))
            for class_data in classes_conf
        ]
        self.annotator = annotator or self._create_annotator()
        self.detections = []
        self.annotations: list[ImageAnnotation] = []

    def _create_annotator(self) -> Sam3Annotator:
        classes = [
            ClassConfig.from_values(
                class_data["class_name"],
                [item["search_query"] for item in class_data.get("subclasses", [])
                 if item.get("search_query")],
            )
            for class_data in self.classes_conf
            if class_data.get("subclasses")
        ]
        return Sam3Annotator(AnnotationConfig.for_classes(
            classes,
            self.configuration.get(
                "sam3_weights_path",
                os.path.join(get_appdata_dir("models"), "sam3.pt"),
            ),
            device=self.configuration.get("sam3_device", "cpu"),
            confidence=self.configuration.get("sam3_confidence", 0.15),
            min_box_area_px=self.configuration.get("sam3_min_box_area_px", 100.0),
            one_detection_per_class=self.configuration.get("sam3_one_detection_per_class", False),
        ))


    def calculate_bboxes_data(self, allowed_class_ids: set[int] | None = None) -> list[dict]:
        self.annotations, annotations_data = [], []
        self.detections = self.annotator.annotate(Image.fromarray(self.image))
        for detection in self.detections:
            class_id = self.class_ids[detection.class_id]
            if allowed_class_ids is not None and class_id not in allowed_class_ids:
                continue
            x1, y1, x2, y2 = map(round, detection.box_xyxy)
            contour = np.array([[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]], dtype=np.int32)
            annotation = ImageAnnotation(contour, self.image.shape[:2][::-1])
            data = annotation.get()
            data["class_id"] = class_id
            data["score"] = detection.score
            annotations_data.append(data)
            self.annotations.append(annotation)
        return annotations_data


    def put_contours_on_image(self, array_image: MatLike, contours: tuple[int]=(),
                              hull_contours: tuple[int]=(), rectangles: tuple[int]=(0, 0, 255)) -> MatLike:
        array_image_new = array_image.copy()
        for annotation in self.annotations:
            array_image_new = annotation.put_contour_on_image(array_image_new, contours, hull_contours, rectangles)
        return array_image_new