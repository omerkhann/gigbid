## Overview
`policy-rag` is a Retrieval‑Augmented Generation (RAG) service that ingests ~4,000 internal policy PDFs, indexes their content, and exposes a conversational API for answering policy‑related queries with source citations. The system is built in Python and designed for batch ingestion, incremental updates, and low‑latency inference.

## Architecture
- **Ingestion pipeline**: A Celery worker reads PDFs, extracts text with `pdfminer.six`, splits it into overlapping chunks (≈200 tokens), and stores the chunks in a vector store (FAISS). Metadata (document ID, page number) is attached to each vector for citation.
- **Embedding service**: Chunk embeddings are generated via a hosted OpenAI `text-embedding-ada-002` endpoint. Embeddings are persisted in the FAISS index.
- **API layer**: A FastAPI server provides two endpoints: `/search` returns the top‑k relevant chunks with metadata; `/ask` runs the full RAG flow. The ask endpoint retrieves relevant chunks, concatenates them with the user prompt, and forwards the combined prompt to a LLM (e.g., GPT‑4o) for answer generation.
- **Citation handling**: The LLM is prompted to cite sources using the supplied metadata. The response includes a list of document IDs and page numbers that can be cross‑referenced.
- **Task queue**: Celery with Redis broker handles asynchronous ingestion and re‑indexing without blocking the API.

## Setup & Execution
1. **Clone & install**
   ```bash
   git clone https://github.com/yourusername/policy-rag.git
   cd policy-rag
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure environment** (create a `.env` file)
   ```
   OPENAI_API_KEY=your_key_here
   REDIS_URL=redis://localhost:6379/0
   ```
3. **Start Redis** (required for Celery)
   ```bash
   docker run -d -p 6379:6379 redis:7
   ```
4. **Launch Celery worker**
   ```bash
   celery -A rag_worker worker --loglevel=info
   ```
5. **Run the API server**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
6. **Ingest PDFs**
   ```bash
   python scripts/ingest.py --source path/to/pdfs
   ```
   The script will push tasks to Celery; once completed, the FAISS index is ready.

## Usage Example
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the deductible for auto claims?"}'
```
The response includes the answer and a citation list referencing the original PDF and page.

## Testing
Run the pytest suite with `pytest -q` to verify ingestion, retrieval, and citation formatting.
