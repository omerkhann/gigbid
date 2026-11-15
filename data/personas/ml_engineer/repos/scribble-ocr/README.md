# scribble-ocr

## Overview
`scribble-ocr` is a TensorFlow‑based pipeline that converts scanned handwritten patient forms into structured digital records. The system focuses on extracting alphanumeric fields from doctors' notes with a character‑level accuracy of ~94%, eliminating the need for manual data entry.

## Architecture
1. **Ingestion** – Images are uploaded to a local or network‑mounted directory. A watchdog service detects new files and queues them for processing.
2. **Pre‑processing** – Each image undergoes grayscale conversion, adaptive thresholding, and deskewing using OpenCV. The pipeline also extracts regions of interest (ROIs) based on a configurable template that maps form fields to bounding boxes.
3. **Model Inference** – A CNN‑RNN hybrid model (CNN for feature extraction, Bi‑LSTM for sequence modeling) built with TensorFlow 2.x processes each ROI. The model outputs a softmax over the character set and is decoded with a CTC loss‑based beam search.
4. **Post‑processing** – Raw character strings are cleaned (e.g., removing spurious symbols) and validated against field‑specific regex patterns. Validated entries are written to a PostgreSQL database.
5. **Orchestration** – Docker Compose defines three services: `watcher`, `ocr_worker`, and `db`. Logs are collected via the Docker logging driver.

## Getting Started
```bash
# Clone the repo
git clone https://github.com/yourusername/scribble-ocr.git
cd scribble-ocr

# Build and start services
docker compose up --build -d
```
Place scanned form images into `./data/incoming`. Processed files will appear in `./data/processed` and the extracted data will be stored in the `ocr_results` table of the PostgreSQL container.

## Training / Retraining
The `train/` directory contains a Jupyter notebook that demonstrates dataset preparation, model definition, and training loops. Adjust the `config.yaml` to point to your annotated dataset and run:
```bash
docker exec -it scribble-ocr_ocr_worker_1 python train/train.py --config config.yaml
```

## Testing
Unit tests are located in `tests/`. Run them with:
```bash
pytest tests/
```

## License
MIT License.
