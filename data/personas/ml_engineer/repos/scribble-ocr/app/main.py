import os
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import numpy as np
import cv2
import tensorflow as tf
from google.cloud import storage

app = FastAPI(title="Handwritten OCR API")

# Load model once at startup
MODEL_BUCKET = "handwritten-ocr-models"
MODEL_PATH   = "latest/model.h5"

def load_model_from_gcs(bucket_name: str, model_path: str) -> tf.keras.Model:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob   = bucket.blob(model_path)
    temp_file = "/tmp/model.h5"
    blob.download_to_filename(temp_file)
    return tf.keras.models.load_model(temp_file)

model = load_model_from_gcs(MODEL_BUCKET, MODEL_PATH)

CHAR_MAP = {i: chr(32 + i) for i in range(95)}


def preprocess(img_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(img_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Invalid image data")
    img = cv2.resize(img, (28, 28))
    img = img.astype(np.float32) / 255.0
    img = np.expand_dims(img, axis=(0, -1))
    return img

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        img      = preprocess(contents)
        probs    = model.predict(img)[0]
        idx      = int(np.argmax(probs))
        char     = CHAR_MAP.get(idx, "?")
        return JSONResponse(content={"filename": file.filename, "character": char})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
