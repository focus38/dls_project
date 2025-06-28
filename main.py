import os
import uvicorn
import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, UploadFile, HTTPException
from common.exceptions import ImageNotFoundException

from services.detector_service import DetectorService

DETECTOR_MODEL_PATH = './models/emeter_yolo11n_v1.pt'
OCR_MODEL_PATH = './models/emeter_ocr_v1.pt'

# Глобальный экземпляр сервиса
detector_service = None
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector_service
    try:
        detector_service = await DetectorService(DETECTOR_MODEL_PATH, OCR_MODEL_PATH).initialize()
        yield
    finally:
        await detector_service.cleanup()
        detector_service = None
        print("Resources released.")

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

# Роут для загрузки изображения.
@app.post("/upload/")
async def upload_image(file: UploadFile):
    return await detector_service.handle_upload(file)

# Роут для проверки статуса изображения.
@app.get("/status/{image_uuid}")
async def check_status(image_uuid: str):
    try:
        return await detector_service.check_status(image_uuid)
    except Exception as ex:
        logger.error(f"Error while get image status. {ex}", exc_info=True)
        if isinstance(ex, ImageNotFoundException):
            raise HTTPException(status_code=404, detail=ex.message)
        else:
            raise HTTPException(status_code=500, detail='Some error occurred.')

# Роут для получения обработанного изображения.
@app.get("/result/{image_uuid}")
async def get_result(image_uuid: str):
    try:
        file_path = await detector_service.get_result(image_uuid)
        return FileResponse(file_path)
    except Exception as ex:
        logger.error(f"Error while get image result. {ex}", exc_info=True)
        if isinstance(ex, ImageNotFoundException):
            raise HTTPException(status_code=404, detail=ex.message)
        else:
            raise HTTPException(status_code=500, detail='Some error occurred.')

# Роут для получения распознанных значений счетчика.
@app.get("/values/{image_uuid}")
async def get_values(image_uuid: str):
    try:
        values = await detector_service.get_values(image_uuid)
        content = {"values": values}
        return JSONResponse(content=content, status_code=200)
    except Exception as ex:
        logger.error(f"Error while get indicator values. {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail='Some error occurred.')

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")), log_level="info", log_config="log_config.yaml")
