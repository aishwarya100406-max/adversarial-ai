import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline import run_investigation

app = FastAPI(title="Adversarial Verification Graph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvestigateRequest(BaseModel):
    query: str


@app.get("/health")
def health():
    return {"ok": True, "has_api_key": bool(os.environ.get("GROQ_API_KEY"))}


@app.post("/investigate")
def investigate(req: InvestigateRequest):
    if not req.query.strip():
        raise HTTPException(400, "query is required")
    log: list[str] = []
    try:
        result = run_investigation(req.query, log)
    except Exception as e:
        raise HTTPException(500, f"pipeline failed: {e}\nlog: {log}")
    return result
