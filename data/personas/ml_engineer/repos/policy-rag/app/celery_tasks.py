from celery import Celery
from sqlalchemy import create_engine, text
from app.nlp import process_text

# Celery configuration
app = Celery('rag_assistant', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')
app.conf.update(task_serializer='json', result_serializer='json', accept_content=['json'])

# Database connection
engine = create_engine('postgresql://user:password@localhost:5432/policies')

@app.task
def index_policy(policy_id: int, raw_text: str):
    """Process a policy document and store embeddings in the database."""
    # Process text: tokenize, clean, embed
    embedding = process_text(raw_text)
    # Store embedding and metadata
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO policy_embeddings (policy_id, embedding) VALUES (:id, :emb)"),
            {'id': policy_id, 'emb': embedding}
        )
    return {'status': 'indexed', 'policy_id': policy_id}

@app.task
def answer_query(query: str, top_k: int = 5):
    """Return top-k relevant policy passages for a user query."""
    # Compute query embedding
    query_emb = process_text(query)
    # Retrieve top-k similar embeddings
    with engine.connect() as conn:
        results = conn.execute(
            text(
                """
                SELECT policy_id, passage_text, similarity(embedding, :qemb) AS score
                FROM policy_passages
                ORDER BY score DESC
                LIMIT :k
                """
            ),
            {'qemb': query_emb, 'k': top_k}
        ).fetchall()
    # Format results
    return [{'policy_id': r['policy_id'], 'text': r['passage_text'], 'score': r['score']} for r in results]
