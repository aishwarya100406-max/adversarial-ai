# Adversarial Verification Graph — OSINT Investigative Agent

Pipeline: Planner -> Retrieval -> Claim Extraction -> Red-Team -> Confidence Synthesis.
Output is an interactive claim graph (not a text report) — every claim node shows its
supporting/contradicting sources, an independence-adjusted confidence score with the
formula shown inline, and a red-team agent's rebuttal.

## Backend setup

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # then paste your ANTHROPIC_API_KEY into .env
uvicorn main:app --reload --port 8000
```

Health check: http://localhost:8000/health

## Frontend setup

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, enter an investigative question, click Investigate.

## Notes

- Web search uses `ddgs` (no API key needed) and `trafilatura` to pull full article text
  for better claim extraction than snippet-only.
- Source independence: sources are clustered by publisher (e.g. wire-service reprints
  collapse into one cluster) so claims backed only by syndicated copies of one story get
  penalized in the confidence formula, visible in the UI.
- The Red-Team agent runs as a separate LLM call per claim with an adversarial system
  prompt (causal overreach, independence collapse, recency, conflict of interest,
  methodology weakness) — its rebuttal strength directly lowers the claim's confidence.
- This is a hackathon MVP: graph is in-memory per request (no persistence store). Swap in
  Neo4j if you want cross-investigation graph queries.
