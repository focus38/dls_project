import os
import uuid
import asyncio

from pathlib import Path
from typing import Dict, List
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, UploadFile, HTTPException

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

# Конфигурация.
TEMP_IMAGE_FOLDER = "temp"
os.makedirs(TEMP_IMAGE_FOLDER, exist_ok=True)

# Очереди и хранилища.
processing_queue: asyncio.Queue[str] = asyncio.Queue()
processed_images: Dict[str, str] = {}  # uuid -> filepath
processing_tasks: Dict[str, asyncio.Task] = {}  # uuid -> task

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

# Функция обработки изображения. Пока заглушка.
async def process_image(image_uuid: str, input_path: str):
    try:
        # Здесь будет логика обработки изображения.
        # Пока для примера ждем 10 секунд.
        await asyncio.sleep(10)
        
        # Сохраняем "обработанное" изображение.
        output_path = os.path.join(TEMP_IMAGE_FOLDER, f"processed_{image_uuid}.jpg")
        Path(input_path).rename(output_path)
        
        # Добавляем в список готовых изображений.
        processed_images[image_uuid] = output_path
    finally:
        # Удаляем задачу из списка активных.
        processing_tasks.pop(image_uuid, None)

# Фоновая задача для обработки очереди.
async def process_queue():
    while True:
        image_uuid = await processing_queue.get()
        input_path = os.path.join(TEMP_IMAGE_FOLDER, f"{image_uuid}.jpg")
        
        # Создаем задачу на обработку и сохраняем ссылку на нее.
        task = asyncio.create_task(process_image(image_uuid, input_path))
        processing_tasks[image_uuid] = task
        
        # Помечаем задачу, как выполненную в очереди.
        processing_queue.task_done()

# Запускаем обработчик очереди при старте приложения.
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(process_queue())

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
        raise HTTPException(status_code=404, detail="Image not found")

# Роут для получения обработанного изображения.
@app.get("/result/{image_uuid}")
async def get_result(image_uuid: str):
    if image_uuid not in processed_images:
        raise HTTPException(status_code=404, detail="Image not processed or not found")
    
    file_path = processed_images[image_uuid]
    return FileResponse(file_path)
