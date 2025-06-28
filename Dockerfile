FROM python:3.9-slim-buster as builder

WORKDIR /app

COPY requirements.txt /app/
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

FROM python:3.9-slim-buster as runner

WORKDIR /app

COPY --from=builder /app/wheels /app/wheels
COPY --from=builder /app/requirements.txt .
RUN apt-get update && \
    apt-get install -y libgl1-mesa-glx libgtk2.0-dev && \
    pip install --no-cache-dir /app/wheels/* && pip install --no-cache-dir uvicorn

# Copy project
COPY . /app/

# Define the command to start the container
CMD python main.py
