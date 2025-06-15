import os
import uuid
import asyncio

from PIL import Image
from pathlib import Path
from typing import Dict, List

from contextlib import asynccontextmanager
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, UploadFile, HTTPException

from detector import ElectricMeterDetector

# Конфигурация.
TEMP_IMAGE_FOLDER = "temp"

# Очереди и хранилища.
processing_queue = asyncio.Queue()
processed_images: Dict[str, str] = {} # uuid -> filepath
processing_tasks: Dict[str, asyncio.Task] = {} # uuid -> task

detector = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector
    try:
        detector = await ElectricMeterDetector().load_model()
        
        # Создаем временную папку для изображений.
        os.makedirs(TEMP_IMAGE_FOLDER, exist_ok=True)
        
        # Запуск обработчика очереди.
        asyncio.create_task(process_queue())
        yield
    finally:
        # Очистка ресурсов.
        detector.release_resource()
        detector = None
        print("Resources released.")

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

# Роут для загрузки изображения.
@app.post("/upload/")
async def upload_image(file: UploadFile):
    # Генерируем идентификатор для изображения.
    image_uuid = str(uuid.uuid4())
    
    # Сохраняем изображение во временную папку.
    file_path = os.path.join(TEMP_IMAGE_FOLDER, f"{image_uuid}.jpg")
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Добавляем в очередь на обработку.
    await processing_queue.put(image_uuid)
    
    return {"uuid": image_uuid, "status": "queued"}

# Роут для проверки статуса изображения.
@app.get("/status/{image_uuid}")
async def check_status(image_uuid: str):
    if image_uuid in processed_images:
        return {"status": "processed"}
    elif image_uuid in processing_tasks:
        return {"status": "processing"}
    else:
        raise HTTPException(status_code=404, detail="Image not found.")

# Роут для получения обработанного изображения.
@app.get("/result/{image_uuid}")
async def get_result(image_uuid: str):
    if image_uuid not in processed_images:
        raise HTTPException(status_code=404, detail="Image not processed or not found.")
    
    file_path = processed_images[image_uuid]
    return FileResponse(file_path)

# Фоновая задача для обработки очереди.
async def process_queue():
    while True:
        image_uuid = await processing_queue.get()
        input_path = os.path.join(TEMP_IMAGE_FOLDER, f"{image_uuid}.jpg")
        # Создаем задачу для обработки изображения и сохраняем ссылку на нее.
        task = asyncio.create_task(process_queue_item(image_uuid, input_path))
        processing_tasks[image_uuid] = task
        # В очереди на обработку помечаем задачу, как выполненную.
        processing_queue.task_done()

async def process_queue_item(image_uuid: str, input_path: str):
    try:
        def sync_process_image():
            return detector.process_image(image_uuid, input_path)
        
        detector_result = await asyncio.get_event_loop().run_in_executor(None, sync_process_image)
        
        output_path = os.path.join(TEMP_IMAGE_FOLDER, f"processed_{image_uuid}.jpg")
        detector_image = detector_result.plot()
        result_image = Image.fromarray(detector_image[..., ::-1])
        result_image.save(output_path)
        processed_images[image_uuid] = output_path
    except Exception as e:
        print(f"Error occurred while processing the image {image_uuid}: {e}")
        print(traceback.format_exc())
        raise
    finally:
        processing_tasks.pop(image_uuid, None)
