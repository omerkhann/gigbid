import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib

app = FastAPI(title="Support Ticket Triage API")

class Ticket(BaseModel):
    subject: str
    description: str

class Prediction(BaseModel):
    category: str
    confidence: float

# Load pre‑trained model and vectorizer
model = joblib.load("models/triage_model.pkl")
vectorizer = joblib.load("models/vectorizer.pkl")

@app.post("/predict", response_model=Prediction)
async def predict(ticket: Ticket):
    try:
        text = f"{ticket.subject} {ticket.description}"
        X = vectorizer.transform([text])
        probs = model.predict_proba(X)[0]
        idx = probs.argmax()
        category = model.classes_[idx]
        confidence = float(probs[idx])
        return Prediction(category=category, confidence=confidence)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}
