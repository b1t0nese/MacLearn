import cv2
from cv2.typing import MatLike
import numpy as np
import rembg
import random



def open_image(file_path: str) -> MatLike:
    with open(file_path, 'rb') as f:
        img_array = np.frombuffer(f.read(), dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return image


def resize_image(img: MatLike, target_size: tuple=(300, 300)) -> MatLike:
    height, width = img.shape[:2]
    scale = min(target_size[0] / width, target_size[1] / height)
    new_width, new_height = int(width * scale), int(height * scale)
    resized_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
    return resized_img


def distort_image(img: MatLike, distortion_type=None, fill_color=None) -> MatLike:
    if distortion_type is None:
        distortion_type = random.choice(["blur", "noise", "rotation", "perspective"])
    if fill_color is None:
        fill_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

    if distortion_type == "blur":
        blur_amount = random.randint(3, 15)
        if blur_amount % 2 == 0:
            blur_amount += 1
        distorted_img = cv2.GaussianBlur(img, (blur_amount, blur_amount), 0)
    elif distortion_type == "noise":
        row, col, ch = img.shape
        noise_level = random.randint(0, 10)
        gauss = np.random.normal(0, noise_level, (row, col, ch)).astype('uint8')
        distorted_img = cv2.add(img, gauss)
    elif distortion_type == "rotation":
        angle = random.randint(-30, 30)
        height, width = img.shape[:2]
        center = (width // 2, height // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        distorted_img = cv2.warpAffine(img, rotation_matrix, (width, height), borderValue=fill_color)
    elif distortion_type == "perspective":
        height, width = img.shape[:2]
        max_offset = min(width, height) // 4
        pts1 = np.float32([[0, 0], [width, 0], [0, height], [width, height]])
        offset1 = (random.randint(0, max_offset), random.randint(0, max_offset))
        offset2 = (width - random.randint(0, max_offset), random.randint(0, max_offset))
        offset3 = (random.randint(0, max_offset), height - random.randint(0, max_offset))
        offset4 = (width - random.randint(0, max_offset), height - random.randint(0, max_offset))
        pts2 = np.float32([offset1, offset2, offset3, offset4])
        matrix = cv2.getPerspectiveTransform(pts1, pts2)
        distorted_img = cv2.warpPerspective(img, matrix, (width, height), borderMode=cv2.BORDER_CONSTANT, borderValue=fill_color)
    else:
        distorted_img = None

    return distorted_img



class ImageAnnotation:
    def formate_bbox(bbox: tuple[int], img_size: tuple[int]=None,
                     new_img_size: tuple[int]=None, type: str=None) -> str:
        """
        Formate bbox for new image or other annotation type

        :param bbox: bounding box data of the type (x, y, w, h)
        :type bbox: tuple[int]
        :param img_size: Optionally: (w, h) of the image in which the bbox was received, it is necessary for type="YOLO" or when resizing the image
        :type img_size: tuple[int] = None
        :param new_img_size: Optionally: (w, h) of the image to create a new annotation for
        :type new_img_size: tuple[int] = None
        :param type: the name of the annotation type used, available: "YOLO", "COCO", "PASCAL_VOC", None (default bbox)
        :type type: str = "COCO"
        :return: formatted annotation as string
        """
        end_img_size = new_img_size if new_img_size else img_size

        if img_size and new_img_size:
            (w1, h1), (w2, h2) = img_size, new_img_size
            scale_x, scale_y = w2 / w1, h2 / h1
            x, y, w, h = bbox
            x, w = int(x * scale_x), int(w * scale_x)
            y, h = int(y * scale_y), int(h * scale_y)
            bbox = (x, y, w, h)
        else:
            x, y, w, h = bbox

        if type=="YOLO" and end_img_size:
            yolo_x_center, yolo_y_center = (x + w/2) / img_size[0], (y + h/2) / img_size[1]
            yolo_width, yolo_height = w / img_size[0], h / img_size[1]
            return f"{yolo_x_center:.6f} {yolo_y_center:.6f} {yolo_width:.6f} {yolo_height:.6f}"

        elif type=="COCO":
            return f"[{x}, {y}, {w}, {h}]"

        elif type=="PASCAL_VOC":
            return f"<xmin>{x}</xmin><ymin>{y}</ymin><xmax>{x+w}</xmax><ymax>{y+h}</ymax>"
    
        else:
            return bbox


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
        self.bbox_yolo = ImageAnnotation.formate_bbox(bbox, self.img_size, type="YOLO")
        self.bbox_coco = ImageAnnotation.formate_bbox(bbox, type="COCO")
        self.bbox_pascal_voc = ImageAnnotation.formate_bbox(bbox, type="PASCAL_VOC")


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



def main():
    from PIL import Image
    my_photo = Image.open(input("Введите путь к изображению: "))
    if not my_photo:
        return
    image = cv2.cvtColor(np.array(my_photo), cv2.COLOR_RGB2BGR)

    object_detector = ImageAnnotationDetector(image)
    object_detector.remove_bg()
    object_detector.detect_contours()
    object_detector.smooth_contours()
    object_detector.filter_contours_to_needed()

    annotation_data = object_detector.calculate_bboxes_data()
    if annotation_data:
        print(annotation_data[0])

        cv2.imshow('Detected', object_detector.put_contours_on_image(image))
        cv2.waitKey(0)
        cv2.destroyAllWindows()



if __name__=="__main__":
    main()