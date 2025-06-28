import cv2
import torch
import asyncio
import logging

from models.crnn import CRNN
from torchvision.transforms import v2
from common.decoder import CTCDecoder

class NumbersRecognizer():
    def __init__(self, model_path):
        self.num_of_channels = 3
        self.hidden_size = 256
        self.characters = list(" 0123456789.,")
        self.num_of_chars = len(self.characters) + 1
        self.model_path = model_path
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.logger = logging.getLogger(__name__)
        self.ctc_decoder = CTCDecoder(self.characters)
        self.transform_image = v2.Compose([
            v2.Lambda(self._conditional_rotate),
            v2.Resize((64, 384)), # H, W
            v2.ToImage(),
            v2.ToDtype(torch.float32, scale=True),
            v2.Lambda(self._clahe_transform)
        ])

    async def load_model(self):
        self.model = CRNN(self.num_of_channels, self.num_of_chars, self.hidden_size)
        self.model.to(self.device)
        model_state_dict = torch.load(self.model_path, map_location=torch.device(self.device))
        self.model.load_state_dict(model_state_dict)
        self.model.eval()
        self.logger.info(f"Recognizer loaded. The '{self.device}' device will be used.")
        return self

    # Освобождение ресурсов.
    def release_resource(self):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Функция распознавания показания счетчика из результата работы детектора
    def parse_indicator_values(self, indicator_images: []) -> []:
        result = []
        with torch.no_grad():
            for img in indicator_images:
                image_tensor = self.transform_image(img).unsqueeze(0).to(self.device)
                ocr_output, encoder_out_lens = self.model(image_tensor)
                indicator_value = self.ctc_decoder.decode(ocr_output)
                result.append(indicator_value)
        return result

    def _conditional_rotate(self, img):
        if img.height > img.width:
            return v2.functional.rotate(img, angle=90, expand=True)  # Поворот на 90°
        return img

    def _apply_clahe(self, image):
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        clahe_image = clahe.apply(image)

        if len(clahe_image.shape) == 2:
            clahe_image = cv2.cvtColor(clahe_image, cv2.COLOR_GRAY2RGB)
        return clahe_image
    
    def _clahe_transform(self, image):
        if isinstance(image, torch.Tensor):
            image = image.permute(1, 2, 0).numpy() * 255
            image = image.astype('uint8')

        clahe_image = self._apply_clahe(image)
        clahe_image = torch.from_numpy(clahe_image).permute(2, 0, 1).float() / 255.0
        return clahe_image