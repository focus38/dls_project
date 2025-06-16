import asyncio

from contextlib import asynccontextmanager

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, UploadFile, HTTPException
from common.exceptions import ImageNotFoundException

from services.detector_service import DetectorService

DETECTOR_MODEL_PATH = './models/emeter_yolo11n_v1.pt'

# Глобальный экземпляр сервиса
detector_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector_service
    try:
        detector_service = await DetectorService(DETECTOR_MODEL_PATH).initialize()
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
        if isinstance(ex, ImageNotFoundException):
            raise HTTPException(status_code=404, detail=ex.message)
        else:
            raise HTTPException(status_code=500, detail='Some error occurred.')
