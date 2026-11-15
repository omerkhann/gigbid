import cv2
import numpy as np
import tensorflow as tf
from google.cloud import storage

# Load a pre‑trained model (saved in GCS bucket)
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

# Character mapping (index → character)
CHAR_MAP = {i: chr(32 + i) for i in range(95)}  # ASCII printable chars


def preprocess_image(img_path: str) -> np.ndarray:
    """Read an image, convert to grayscale, resize to 28x28 and normalize."""
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Image not found: {img_path}")
    img = cv2.resize(img, (28, 28))
    img = img.astype(np.float32) / 255.0
    img = np.expand_dims(img, axis=(0, -1))  # shape: (1, 28, 28, 1)
    return img


def predict_character(img_array: np.ndarray) -> str:
    probs = model.predict(img_array)[0]
    idx   = np.argmax(probs)
    return CHAR_MAP.get(idx, "?")


def ocr_document(image_folder: str, output_csv: str) -> None:
    import os
    import csv

    rows = []
    for filename in os.listdir(image_folder):
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue
        img_path = os.path.join(image_folder, filename)
        img      = preprocess_image(img_path)
        char     = predict_character(img)
        rows.append([filename, char])

    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['image', 'predicted_char'])
        writer.writerows(rows)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OCR on handwritten clinic forms")
    parser.add_argument("--input_dir", required=True, help="Directory of scanned form images")
    parser.add_argument("--output", required=True, help="CSV file to write predictions")
    args = parser.parse_args()
    ocr_document(args.input_dir, args.output)
