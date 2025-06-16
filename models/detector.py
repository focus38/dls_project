import uuid
import torch
import asyncio

from PIL import Image
from ultralytics import YOLO

class ElectricMeterDetector():
    def __init__(self, model_path='emeter_yolo11n_v1.pt'):
        self.conf_threshold = 0.59
        self.model_path = model_path
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

    async def load_model(self):
        self.model = YOLO(self.model_path)
        self.model.to(self.device)
        print(f"Detector loaded. The '{self.device}' device will be used.")
        return self

    # Освобождение ресурсов.
    def release_resource(self):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    # Функция детекции на загруженном изображении.
    def process_image(self, image_uuid: str, input_path: str):
        img = Image.open(input_path)
        detector_results = self.model.predict(source=img, conf=self.conf_threshold, save=False, device=self.device)
        return detector_results[0]
