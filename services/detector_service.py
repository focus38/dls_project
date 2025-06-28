import os
import uuid
import torch
import asyncio
import logging
from typing import Dict

from PIL import Image
from fastapi import UploadFile

from datetime import datetime, timedelta
from models.recognizer import NumbersRecognizer
from models.detector import ElectricMeterDetector

from common.exceptions import ImageNotFoundException

class DetectorService:
    TEMP_IMAGE_FOLDER = "temp"
    
    def __init__(self, detector_model_path, recognizer_model_path):
        self.detector = None
        self.recognizer = None
        self.detector_model_path = detector_model_path
        self.recognizer_model_path = recognizer_model_path
        self.processing_queue = asyncio.Queue()
        # Хранилище информации о файлах: {file_id: {"original": path, "processed": path, "timestamp": datetime}}
        self.processed_images: Dict[str, Dict[str, str]] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}  # uuid -> task
        self.file_lifetime = 120 # 2 минуты
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        self.detector = await ElectricMeterDetector(self.detector_model_path).load_model()
        self.recognizer = await NumbersRecognizer(self.recognizer_model_path).load_model()
        # Создаем временную папку для изображений.
        os.makedirs(self.TEMP_IMAGE_FOLDER, exist_ok=True)
        # Запуск обработчика очереди.
        asyncio.create_task(self._process_queue())
        # Очистка файлов и внутренних словарей
        asyncio.create_task(self._cleanup_old_files())
        return self

    # Очистка ресурсов.
    async def cleanup(self):
        if self.detector:
            self.detector.release_resource()
            self.recognizer.release_resource()
            self.detector = None
            self.recognizer = None

    async def handle_upload(self, file: UploadFile):
        # Генерируем идентификатор для изображения.
        image_uuid = str(uuid.uuid4())
        self.logger.info(f"Upload file with ID {image_uuid}.")
        # Сохраняем изображение во временную папку.
        file_path = os.path.join(self.TEMP_IMAGE_FOLDER, f"{image_uuid}.jpg")
        
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        # Добавляем в очередь на обработку.
        await self.processing_queue.put(image_uuid)
        self.logger.info(f"Put file {image_uuid} to processing queue.")
        return {"uuid": image_uuid, "status": "queued"}

    async def check_status(self, image_uuid: str):
        if image_uuid in self.processed_images:
            return {"status": "processed"}
        elif image_uuid in self.processing_tasks:
            return {"status": "processing"}
        else:
            raise ImageNotFoundException(message="Image not found.")

    async def get_result(self, image_uuid: str):
        if image_uuid not in self.processed_images:
            raise ImageNotFoundException(message="Image not processed or not found.")

        process_image = self.processed_images[image_uuid]
        return process_image["output_path"]

    async def get_values(self, image_uuid: str):
        if image_uuid not in self.processed_images:
            raise ImageNotFoundException(message="Image not processed or not found.")
        
        process_image = self.processed_images[image_uuid]
        return process_image["values"]

    # Функция для обработки очереди. Работает как фоновая задача.
    async def _process_queue(self):
        while True:
            image_uuid = await self.processing_queue.get()
            input_path = os.path.join(self.TEMP_IMAGE_FOLDER, f"{image_uuid}.jpg")

            # Создаем задачу для обработки изображения и сохраняем ссылку на нее.
            task = asyncio.create_task(self._process_image(image_uuid, input_path))
            self.processing_tasks[image_uuid] = task
            # В очереди на обработку помечаем задачу, как выполненную.
            self.processing_queue.task_done()

    # Функция обработки конретного изображения.
    async def _process_image(self, image_uuid: str, input_path: str):
        try:
            def sync_process_image():
                img = Image.open(input_path)
                detector_result = self.detector.process_image(image_uuid, img)
                if detector_result is None:
                    return [], detector_result
                indicator_indices = torch.isclose(detector_result.boxes.cls, torch.tensor(self.detector.indicator_class_index)).nonzero()
                if len(indicator_indices) <= 0:
                    return [], detector_result
                indicator_indices = indicator_indices.flatten().cpu().numpy().astype(int)
                indicator_boxes = detector_result.boxes.xyxy[indicator_indices].cpu().numpy().astype(int)
                indicator_images = []
                for j, bbox in enumerate(indicator_boxes):
                    x1, y1, x2, y2 = bbox
                    cropped_img = img.crop((x1, y1, x2, y2))
                    indicator_images.append(cropped_img)
                if len(indicator_images) == 0:
                    return [], detector_result
                indicator_values = self.recognizer.parse_indicator_values(indicator_images)
                return indicator_values, detector_result
            
            values, detector_result = await asyncio.get_event_loop().run_in_executor(None, sync_process_image)
            
            output_path = os.path.join(self.TEMP_IMAGE_FOLDER, f"processed_{image_uuid}.jpg")
            detector_image = detector_result.plot()
            result_image = Image.fromarray(detector_image[..., ::-1])
            result_image.save(output_path)
            self.processed_images[image_uuid] = {
                "input_path": input_path,
                "output_path": output_path,
                "timestamp": datetime.now(),
                "values": values
            }
            self.logger.info(f"File {image_uuid} processed.")
        except Exception as e:
            self.logger.error(f"Error occurred while processing the image {image_uuid}: {e}", exc_info=True)
            raise
        finally:
            self.processing_tasks.pop(image_uuid, None)

    # Удаляет файлы старше file_lifetime секунд.
    async def _cleanup_old_files(self):
        while True:
            await asyncio.sleep(30)  # Проверка каждые 30 секунд
            self.logger.info("Deleting old files has started.")
            current_time = datetime.now()
            to_delete = []
    
            for image_uuid, file_data in self.processed_images.items():
                file_time = file_data["timestamp"]
                if (current_time - file_time) > timedelta(seconds=self.file_lifetime):
                    to_delete.append(image_uuid)
                    try:
                        if os.path.exists(file_data["input_path"]):
                            os.unlink(file_data["input_path"])
                        if os.path.exists(file_data["output_path"]):
                            os.unlink(file_data["output_path"])
                    except Exception as e:
                        self.logger.error(f"Ошибка удаления файла {image_uuid}: {e}", exc_info=True)
    
            for image_uuid in to_delete:
                self.processed_images.pop(image_uuid, None)
