import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncpg
from transformers import pipeline

app = FastAPI(title="Law Firm Q&A Chatbot")

# Load a small question‑answering pipeline
qa_pipeline = pipeline("question-answering")

# Database connection pool
DB_DSN = os.getenv("POSTGRES_DSN", "postgresql://user:pass@localhost:5432/lawfirm")
pool = None

class QARequest(BaseModel):
    question: str
    context_id: str | None = None

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(dsn=DB_DSN)

@app.on_event("shutdown")
async def shutdown():
    await pool.close()

async def fetch_context(context_id: str) -> str:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT content FROM legal_contexts WHERE id = $1", context_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Context not found")
        return row["content"]

@app.post("/qa")
async def answer(request: QARequest):
    # Retrieve legal context if provided
    context = ""
    if request.context_id:
        context = await fetch_context(request.context_id)
    # Run the NLP model
    result = qa_pipeline({
        "question": request.question,
        "context": context or None
    })
    answer_text = result.get("answer", "I’m sorry, I don’t have an answer.")
    # Log the interaction
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO qa_logs (question, answer, context_id) VALUES ($1, $2, $3)",
            request.question,
            answer_text,
            request.context_id
        )
    return JSONResponse({"answer": answer_text})

# Simple health‑check endpoint
@app.get("/health")
async def health():
    return {"status": "ok"}
