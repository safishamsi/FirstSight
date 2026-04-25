FROM python:3.11-slim

WORKDIR /app

# System libs required by OpenCV and MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender1 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY preprocess.py .
COPY app/ app/
COPY model/ model/
# model/ contains droop_model.onnx and face_landmarker.task
COPY checkpoints/threshold.json checkpoints/threshold.json

ENV MODEL_PATH=model/droop_model.onnx
ENV THRESHOLD_PATH=checkpoints/threshold.json

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
