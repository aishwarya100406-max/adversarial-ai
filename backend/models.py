from pydantic import BaseModel
from typing import Literal, Optional


class Source(BaseModel):
    id: str
    url: str
    title: str
    domain: str
    publisher_cluster: str  # entities sharing this cluster are treated as non-independent
    reliability_tier: Literal["primary", "secondary", "tertiary"]
    reliability_score: float  # 0-1
    snippet: str


class Edge(BaseModel):
    source_id: str
    claim_id: str
    stance: Literal["supports", "contradicts", "neutral"]
    stance_confidence: float  # 0-1, how clearly this source takes that stance


class Rebuttal(BaseModel):
    text: str
    rebuttal_type: Literal[
        "causal_overreach",
        "independence_collapse",
        "recency_superseded",
        "conflict_of_interest",
        "methodology_weakness",
        "no_rebuttal_found",
    ]
    strength: float  # 0-1


class Claim(BaseModel):
    id: str
    text: str
    sub_question: str
    edges: list[Edge] = []
    rebuttal: Optional[Rebuttal] = None
    independence_weight: float = 1.0  # penalty applied for source clustering
    confidence: float = 0.0
    confidence_label: Literal["strong", "moderate", "weak", "unverified"] = "unverified"
    confidence_formula: str = ""


class InvestigationResult(BaseModel):
    query: str
    sub_questions: list[str]
    claims: list[Claim]
    sources: list[Source]
    pipeline_log: list[str]
