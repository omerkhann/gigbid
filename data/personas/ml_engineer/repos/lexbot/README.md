## Overview
`lexbot` is a question‑answering chatbot designed to surface internal legal documents for a law‑firm knowledge base. It ingests PDFs, contracts, and internal memos into a PostgreSQL vector store, then serves user queries via a RESTful API that returns the most relevant passages and a generated answer.

## Architecture
- **Ingestion pipeline** (`ingest.py`):
  - Scans a configured directory for new documents.
  - Extracts text with `pdfminer.six` or `docx2txt`.
  - Splits text into 500‑token chunks, creates embeddings using OpenAI's `text-embedding-ada-002`, and upserts them into a PostgreSQL table with the `pgvector` extension.
- **API layer** (`app.py`):
  - FastAPI server exposing `/query` (POST) and `/health` endpoints.
  - On request, computes query embedding, performs a cosine‑similarity k‑NN search in PostgreSQL, retrieves top‑k chunks, and passes them to the OpenAI `gpt-4o-mini` completion endpoint for answer generation.
- **Cache**: Redis stores recent query embeddings and results to reduce repeat vector searches.
- **Auth**: Simple JWT middleware restricts access to firm employees.

## Running Locally
1. **Prerequisites**: Docker, Python 3.11, PostgreSQL with `pgvector` enabled, Redis.
2. **Setup**:
   ```bash
   cp .env.example .env   # fill in DB credentials and OpenAI API key
   docker compose up -d   # starts postgres, redis, and the FastAPI container
   pip install -r requirements.txt
   python ingest.py --path ./documents
   ```
3. **Start the API**:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```
4. **Query**:
   ```bash
   curl -X POST http://localhost:8000/query \
        -H "Authorization: Bearer <jwt>" \
        -H "Content-Type: application/json" \
        -d '{"question": "What is the firm's policy on data retention?"}'
   ```

## Production Considerations
- Scale the API with a WSGI server (e.g., Gunicorn) behind an Nginx reverse proxy.
- Use managed PostgreSQL with sufficient storage for vector data.
- Rotate OpenAI API keys and enforce rate limits.
- Implement audit logging for query compliance.

`lexbot` reduces routine research time by roughly 30% according to client estimates, allowing associates to focus on higher‑value tasks.
