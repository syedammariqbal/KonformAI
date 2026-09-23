"""Graph state definitions for KonformAI LangGraph orchestrator."""

from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field


class StructuredIntake(BaseModel):
    """Normalized representation of the AI system under evaluation."""

    system_purpose: str = Field(..., description="Primary functional objective of the AI system")
    data_types_used: List[str] = Field(default_factory=list, description="Categories of input data utilized")
    decision_autonomy_level: str = Field(..., description="Autonomy level (e.g. fully autonomous, human-in-the-loop recommendation)")
    affected_persons: str = Field(..., description="Target population or affected parties (e.g. loan applicants, retail consumers)")
    deployment_context: str = Field(..., description="Operating environment, financial sector, or jurisdiction")
    sector: str = Field(default="Banking / Financial Services", description="Industry domain")


class RegulationCitation(BaseModel):
    """Specific statutory citation supporting a regulatory finding."""

    statute: str
    article_section: str
    passage_id: str
    summary: str
    language: str = "en"
    original_text: Optional[str] = None
    translated_text: Optional[str] = None


class GraphState(TypedDict):
    """Comprehensive state dictionary transferred across LangGraph nodes."""

    # Case identifiers
    case_id: str
    system_description: str
    uploaded_doc_paths: List[str]

    # Intake normalization
    structured_intake: Optional[Dict[str, Any]]

    # Security & PII
    injection_detected: bool
    injection_details: Optional[str]
    pii_scan_results: List[Dict[str, Any]]

    # Substantive regulatory evaluations
    eu_ai_act_classification: Optional[Dict[str, Any]]
    bafin_obligations: Optional[Dict[str, Any]]
    has_german_passages: bool
    translated_passages: List[Dict[str, Any]]
    merged_obligations: Optional[Dict[str, Any]]

    # Confidence & routing controls
    classification_confidence: float
    clarification_needed: bool
    clarification_questions: List[str]
    clarification_responses: List[str]
    is_prohibited_practice: bool  # Article 5 hard override flag

    # Gap assessment
    gap_assessment: Optional[Dict[str, Any]]

    # Critic & quality assurance
    critic_verdict: Optional[str]  # APPROVED, REVISE, ESCALATE_HUMAN
    critic_revision_target: Optional[str]
    critic_issues: List[str]
    critic_retry_count: int

    # Final reporting
    final_report: Optional[str]

    # Human-in-the-loop review
    human_review_required: bool
    human_review_decision: Optional[str]  # approve, edit, reject
    human_review_notes: Optional[str]

    # Observability & Audit
    retrieved_passage_ids: List[str]
    token_usage_total: int
    cost_total: float
    langsmith_trace_url: Optional[str]

    # Node tracking
    current_node: str
    graph_status: str  # running, awaiting_clarification, awaiting_human_review, halted_injection, completed, failed
    error_message: Optional[str]
