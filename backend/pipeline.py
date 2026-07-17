import time
import uuid
from models import Claim, Edge, InvestigationResult, Rebuttal, Source
from llm import call_json
from search import web_search, fetch_full_text

PLANNER_SYSTEM = """You are the Planner agent in an OSINT investigation pipeline.
Given a user's investigative question, decompose it into 3-6 atomic, independently
checkable sub-questions. Each sub-question should be narrow enough that a handful of
web searches could gather direct evidence for or against it. Avoid vague sub-questions.

For each sub-question, also produce a short search_query: 4-8 keywords (no question
words like "did", "was", "were", no question marks, no filler) that a search engine
would use to find relevant news articles. Long natural-language questions perform badly
on web search engines, so the search_query must be terse and keyword-based, e.g.
sub_question "Did Boeing issue any airworthiness directives about the door plug before 2024?"
-> search_query "Boeing 737 MAX door plug airworthiness directive".

Return a JSON array of objects:
[{"sub_question": "...", "search_query": "..."}]"""

EXTRACT_SYSTEM = """You are the Claim Extraction agent in an OSINT investigation pipeline.
You will be given a sub-question and a set of source snippets/excerpts (each with an id).
Extract 1-3 atomic factual claims relevant to the sub-question. For each claim, say which
sources support it, contradict it, or are neutral toward it, and how confidently each
source takes that stance.

Return a JSON array of objects:
[{
  "claim_text": "...",
  "stances": [{"source_id": "s1", "stance": "supports"|"contradicts"|"neutral", "stance_confidence": 0.0-1.0}]
}]
Only reference source_ids that were given to you. If no sources meaningfully address the
sub-question, return an empty array."""

REDTEAM_SYSTEM = """You are the Red-Team agent in an OSINT investigation pipeline. Your
ONLY job is to attack a claim that another agent produced. You do not care whether the
claim is popular or well-cited — you look for the single strongest weakness.

Check for, in priority order:
1. causal_overreach: does the claim assert causation when evidence only shows correlation/co-occurrence?
2. independence_collapse: do the "multiple" supporting sources actually trace back to one
   original report/press release/wire story (same publisher_cluster)?
3. recency_superseded: is there reason to believe more recent information could contradict this?
4. conflict_of_interest: do supporting sources have an obvious financial/political stake in this claim being true?
5. methodology_weakness: is the underlying evidence (survey, single anecdote, unverified leak) weak?

If truly nothing meaningful applies, return rebuttal_type "no_rebuttal_found" with low strength.
Return JSON: {"text": "...", "rebuttal_type": "...", "strength": 0.0-1.0}"""


def run_investigation(query: str, log: list[str]) -> InvestigationResult:
    log.append(f"Planner: decomposing query '{query}'")
    plan = call_json(PLANNER_SYSTEM, query)
    if not isinstance(plan, list) or not plan:
        plan = [{"sub_question": query, "search_query": query}]
    plan = [p for p in plan if isinstance(p, dict) and p.get("sub_question") and p.get("search_query")]
    sub_questions = [p["sub_question"] for p in plan]
    log.append(f"Planner produced {len(plan)} sub-questions")

    all_sources: dict[str, Source] = {}
    all_claims: list[Claim] = []

    for i, p in enumerate(plan):
        sq, search_query = p["sub_question"], p["search_query"]
        if i > 0:
            time.sleep(3)  # avoid tripping DDG's rate limiter across sub-questions
        log.append(f"Retrieval: searching for '{search_query}' (sub-question: '{sq}')")
        raw_results = web_search(search_query, max_results=6)
        if not raw_results:
            log.append(f"  no results for '{search_query}'")
            continue

        sub_sources: dict[str, Source] = {}
        excerpts = []
        for r in raw_results:
            sid = "s" + uuid.uuid4().hex[:8]
            text = r["snippet"]
            full = fetch_full_text(r["url"])
            if full:
                text = full[:1200]
            src = Source(
                id=sid,
                url=r["url"],
                title=r["title"],
                domain=r["domain"],
                publisher_cluster=r["publisher_cluster"],
                reliability_tier=r["reliability_tier"],
                reliability_score=r["reliability_score"],
                snippet=r["snippet"][:300],
            )
            sub_sources[sid] = src
            all_sources[sid] = src
            excerpts.append({"source_id": sid, "title": r["title"], "text": text})

        log.append(f"  found {len(sub_sources)} sources, extracting claims")
        extraction_input = (
            f"Sub-question: {sq}\n\nSources:\n"
            + "\n".join(f"[{e['source_id']}] {e['title']}: {e['text']}" for e in excerpts)
        )
        try:
            extracted = call_json(EXTRACT_SYSTEM, extraction_input, max_tokens=2500)
        except ValueError:
            log.append(f"  extraction failed to parse for '{sq}'")
            continue
        if not isinstance(extracted, list):
            continue

        for item in extracted:
            claim_text = item.get("claim_text")
            stances = item.get("stances", [])
            if not claim_text or not stances:
                continue
            cid = "c" + uuid.uuid4().hex[:8]
            edges = [
                Edge(
                    source_id=st["source_id"],
                    claim_id=cid,
                    stance=st.get("stance", "neutral"),
                    stance_confidence=float(st.get("stance_confidence", 0.5)),
                )
                for st in stances
                if st.get("source_id") in sub_sources
            ]
            if not edges:
                continue
            claim = Claim(id=cid, text=claim_text, sub_question=sq, edges=edges)
            all_claims.append(claim)

    log.append(f"Extracted {len(all_claims)} total claims. Running Red-Team pass.")

    for claim in all_claims:
        supporting = [e for e in claim.edges if e.stance == "supports"]
        clusters = {all_sources[e.source_id].publisher_cluster for e in supporting}
        independence_penalty = 0.0
        if len(supporting) > 1 and len(clusters) == 1:
            independence_penalty = 0.4  # all supporters share one origin
        claim.independence_weight = 1.0 - independence_penalty

        redteam_input = (
            f"Claim: {claim.text}\n"
            f"Supporting sources: {[all_sources[e.source_id].title for e in supporting]}\n"
            f"Publisher clusters of supporters: {list(clusters)}\n"
            f"Contradicting sources: {[all_sources[e.source_id].title for e in claim.edges if e.stance == 'contradicts']}"
        )
        try:
            reb = call_json(REDTEAM_SYSTEM, redteam_input, max_tokens=600)
            claim.rebuttal = Rebuttal(**reb)
        except (ValueError, TypeError):
            claim.rebuttal = Rebuttal(text="Red-team check failed to produce output.", rebuttal_type="no_rebuttal_found", strength=0.0)

        support_weight = sum(
            all_sources[e.source_id].reliability_score * e.stance_confidence for e in claim.edges if e.stance == "supports"
        )
        contradict_weight = sum(
            all_sources[e.source_id].reliability_score * e.stance_confidence for e in claim.edges if e.stance == "contradicts"
        )
        rebuttal_strength = claim.rebuttal.strength if claim.rebuttal else 0.0

        raw_confidence = (support_weight - contradict_weight) * claim.independence_weight - rebuttal_strength
        confidence = max(0.0, min(1.0, raw_confidence / max(1.0, support_weight + 0.01)))
        claim.confidence = round(confidence, 3)
        claim.confidence_formula = (
            f"confidence = clamp[((support_weight={support_weight:.2f} - "
            f"contradict_weight={contradict_weight:.2f}) * independence_weight={claim.independence_weight:.2f} "
            f"- rebuttal_strength={rebuttal_strength:.2f}) / support_weight]"
        )
        if claim.confidence >= 0.7:
            claim.confidence_label = "strong"
        elif claim.confidence >= 0.45:
            claim.confidence_label = "moderate"
        elif claim.confidence >= 0.2:
            claim.confidence_label = "weak"
        else:
            claim.confidence_label = "unverified"

    log.append("Synthesis complete.")

    return InvestigationResult(
        query=query,
        sub_questions=sub_questions,
        claims=all_claims,
        sources=list(all_sources.values()),
        pipeline_log=log,
    )
