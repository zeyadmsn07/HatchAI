from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class RunStatus(str, Enum):
    CREATED = "created"
    PHASE_1_RUNNING = "phase_1_running"
    GATE_1_PENDING = "gate_1_pending"
    PHASE_2_RUNNING = "phase_2_running"
    GATE_2_PENDING = "gate_2_pending"
    PHASE_3_RUNNING = "phase_3_running"
    GATE_3_PENDING = "gate_3_pending"
    PHASE_4_RUNNING = "phase_4_running"
    GATE_4_PENDING = "gate_4_pending"
    PHASE_5_RUNNING = "phase_5_running"
    GATE_5_PENDING = "gate_5_pending"
    PHASE_6_RUNNING = "phase_6_running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class GateOutcome(str, Enum):
    GO = "go"
    REPEAT = "repeat"
    PIVOT = "pivot"
    STOP = "stop"


class FounderBrief(BaseModel):
    idea: str
    target_user: str = "ASSUMPTION: general consumers"
    geography: str = "ASSUMPTION: unspecified"
    language: str = "English"
    skills: str = "ASSUMPTION: general"
    budget_usd: float = 0.0
    hours_per_week: float = 10.0
    values: str = "ASSUMPTION: unspecified"
    tech_preference: str = "Python/web"
    assumptions: List[str] = Field(default_factory=list)
    unknown_fields: List[str] = Field(default_factory=list)


class Source(BaseModel):
    key: str
    url: str
    title: str
    domain: str
    fetch_time: str
    text_hash: str
    passages: List[str] = Field(default_factory=list)
    collector: str = ""          # web:<backend> | hn | wikipedia | worldbank
    category: str = ""           # evidence category the query targeted
    # Provenance and freshness (added after the first captures; old snapshots load with defaults
    # and the quality report re-derives what it can from the stored text):
    published: Optional[str] = None                            # YYYY-MM-DD or YYYY, if the page states one
    published_from: str = ""                                   # page-meta | snippet-date | api | ""
    passage_origins: List[str] = Field(default_factory=list)   # per passage: search-snippet | page | api


class Claim(BaseModel):
    category: str
    text: str
    source_keys: List[str] = Field(default_factory=list)
    quote: str = ""
    verified: bool = False
    is_assumption: bool = False


class ResearchFindings(BaseModel):
    claims: List[Claim] = Field(default_factory=list)
    opportunity_angles: List[str] = Field(default_factory=list)
    evidence_score: float = 0.0
    source_count: int = 0
    domain_count: int = 0
    sources: List[Source] = Field(default_factory=list)
    research_round: int = 1
    mode: str = "extractive"     # "llm" or "extractive" (no-LLM, verbatim quotes)
    evidence_mode: str = "live"  # "live" (collected in this run) or "replay" (loaded from a snapshot)
    snapshot: str = ""           # snapshot file + capture time when evidence_mode == "replay"
    scoring_version: str = "v1"  # relevance rule used to classify E's inputs (evidence.SCORING_VERSIONS)


class KillAssumption(BaseModel):
    assumption: str
    risk: str = "medium"
    kill_criterion: str
    evidence_gaps: List[str] = Field(default_factory=list)


class DemandTest(BaseModel):
    channel: str
    metric: str
    threshold: str
    duration_days: int
    cost_usd: float
    status: str = "NOT_RUN"
    # Machine-readable decision rule (pre-registered in Phase 2, applied in Phase 6)
    min_unique_visitors: int = 300
    go_signup_rate: float = 0.10
    stop_signup_rate: float = 0.03


class CanvasBlock(BaseModel):
    block: str
    content: str
    source_keys: List[str] = Field(default_factory=list)
    is_assumption: bool = True


class LeanCanvas(BaseModel):
    problem: CanvasBlock
    customer_segments: CanvasBlock
    unique_value_proposition: CanvasBlock
    solution: CanvasBlock
    channels: CanvasBlock
    revenue_streams: CanvasBlock
    cost_structure: CanvasBlock
    key_metrics: CanvasBlock
    unfair_advantage: CanvasBlock


class Critique(BaseModel):
    summary: str
    riskiest_assumptions: List[KillAssumption] = Field(default_factory=list)
    evidence_score: float = 0.0
    viability_score: float = 0.0
    demand_signal: str = ""
    founder_fit: str = ""
    recommendation: GateOutcome = GateOutcome.STOP
    unresolved_kill_assumptions: int = 0
    viability_breakdown: Dict[str, float] = Field(default_factory=dict)


class GateResult(BaseModel):
    gate_id: int
    outcome: GateOutcome
    evidence_score: float = 0.0
    viability_score: float = 0.0
    reason: str
    checks: Dict[str, bool] = Field(default_factory=dict)
    founder_override: bool = False
    override_reason: str = ""
    pivot_to: str = ""           # suggested new direction when outcome == pivot


class DecisionLogEntry(BaseModel):
    timestamp: str
    agent: str
    action: str
    sources: List[str] = Field(default_factory=list)
    model: Optional[str] = None
    cost: float = 0.0
    approved_by: Optional[str] = None
    run_id: Optional[str] = None
    phase: Optional[int] = None
    outcome: Optional[str] = None
    tokens: Optional[int] = None


# ---------------------------------------------------------------------------
# Phase 3 — MVP generator
# ---------------------------------------------------------------------------

class FieldSpec(BaseModel):
    name: str
    label: str
    type: str = "text"           # text | number | date | datetime | longtext


class FeatureSpec(BaseModel):
    name: str
    description: str
    traces_to: str               # Lean Canvas problem / risk this feature answers
    action: str                  # API action implementing it (verified by generated tests)


class AppSpec(BaseModel):
    product_name: str
    tagline: str
    archetype: str               # key of a template in mvp_templates/
    item_label: str              # e.g. "Flashcard"
    item_label_plural: str
    fields: List[FieldSpec] = Field(default_factory=list)
    seed_items: List[Dict[str, Any]] = Field(default_factory=list)
    features: List[FeatureSpec] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=lambda: ["en"])
    free_tier_limit: int = 50
    target_user: str = ""


class SynonymMatch(BaseModel):
    phrase: str                  # must appear verbatim in the idea
    keyword: str                 # must be an existing keyword of the suggested template


class TemplateSuggestion(BaseModel):
    """LLM task 1 — synonym-aware template suggestion. Code decides whether any of it counts."""
    template: str
    synonyms: List[SynonymMatch] = Field(default_factory=list)


class SpecText(BaseModel):
    """LLM task 2 — product name and tagline for the MVP spec. Text only, never code."""
    product_name: str
    tagline: str
