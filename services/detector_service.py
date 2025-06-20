import os
import uuid
import asyncio
import logging
from typing import Dict

from PIL import Image
from fastapi import UploadFile
from common.exceptions import ImageNotFoundException

from models.detector import ElectricMeterDetector

class DetectorService:
    TEMP_IMAGE_FOLDER = "temp"
    
    def __init__(self, detector_model_path):
        self.detector = None
        self.detector_model_path = detector_model_path
        self.processing_queue = asyncio.Queue()
        self.processed_images: Dict[str, str] = {}  # uuid -> filepath
        self.processing_tasks: Dict[str, asyncio.Task] = {}  # uuid -> task
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        self.detector = await ElectricMeterDetector(self.detector_model_path).load_model()
        # Создаем временную папку для изображений.
        os.makedirs(self.TEMP_IMAGE_FOLDER, exist_ok=True)
        # Запуск обработчика очереди.
        asyncio.create_task(self._process_queue())
        return self

    # Очистка ресурсов.
    async def cleanup(self):
        if self.detector:
            self.detector.release_resource()
            self.detector = None

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
        
        file_path = self.processed_images[image_uuid]
        return file_path

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
                return self.detector.process_image(image_uuid, input_path)
            
            detector_result = await asyncio.get_event_loop().run_in_executor(None, sync_process_image)
            
            output_path = os.path.join(self.TEMP_IMAGE_FOLDER, f"processed_{image_uuid}.jpg")
            detector_image = detector_result.plot()
            result_image = Image.fromarray(detector_image[..., ::-1])
            result_image.save(output_path)
            self.processed_images[image_uuid] = output_path
            self.logger.info(f"File {image_uuid} processed.")
        except Exception as e:
            self.logger.error(f"Error occurred while processing the image {image_uuid}: {e}")
            raise
        finally:
            self.processing_tasks.pop(image_uuid, None)