# `sam3_studio_lib`

Типизированная библиотека автоаннотации для MacLearn на базе SAM3. Она переносит
ядро проекта **SAM3 Dataset Studio** в UI-независимый Python-пакет: текстовые
промпты, аннотация изображений и кадров видео, NMS с подавлением вложенных
дубликатов и экспорт в YOLO.

## Авторство

Эта библиотека была создана на основе кода проекта SAM3 Dataset Studio, автор которого: https://github.com/ArduRadioKot

## Установка

Сначала установите PyTorch под свою платформу, затем зависимости:

```bash
pip install -r src/sam3_studio_lib/requirements.txt
```

Для SAM3 нужны веса `sam3.pt`. Если файла нет, библиотека автоматически загрузит его
из Hugging Face; для закрытого репозитория передайте `HF_TOKEN` (доступ к репозиторию весов
Hugging Face должен быть одобрен).

## Быстрый старт

```python
from pathlib import Path

from sam3_studio_lib import AnnotationConfig, ClassConfig, annotate_images

config = AnnotationConfig.for_classes(
    classes=[
        ClassConfig.from_values("boat", ["blue boat", "boat with green parts"]),
    ],
    weights_path=Path("sam3.pt"),
    device="mps",  # "cpu", "mps" или CUDA-индекс 0
    confidence=0.2,
    one_detection_per_class=False,
)

result = annotate_images(
    ["images/one.jpg", "images/two.jpg"],
    config,
    dataset_dir="dataset",
    zip_path="dataset.zip",
)
print(result.images_with_objects, result.zip_path)
```

Для интеграции с PySide6 передайте `progress(index, total, path)` и вызывайте
`annotate_images` из рабочего `QThread`; библиотека не импортирует Qt или Gradio.

## Публичный API

| Объект | Назначение |
| --- | --- |
| `ClassConfig` | Имя класса и текстовые SAM3-промпты |
| `AnnotationConfig` | Веса, устройство, confidence, NMS и разбиение датасета |
| `Sam3Annotator` | Переиспользуемый SAM3-инференс для PIL-изображений |
| `Detection` | Типизированная рамка `(x1, y1, x2, y2)` и score |
| `annotate_images` | Аннотация списка изображений и необязательный YOLO-экспорт |
| `annotate_video` | Извлечение кадров видео и аннотация |
| `export_yolo` / `zip_dataset` | Экспорт и упаковка датасета |

Модель создаётся один раз на вызов `annotate_images`, поэтому пакетная обработка
намного дешевле последовательного запуска модели для каждого файла.
