"""Central configuration for KonformAI using pydantic-settings.

All environment variables must be loaded through this settings object.
No os.getenv calls scattered elsewhere in the codebase.
"""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ============================================================
    # Application & Environment
    # ============================================================
    PROJECT_NAME: str = "KonformAI"
    API_V1_STR: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    GLOBAL_DRY_RUN: bool = False
    ENABLE_NOTIFICATIONS: bool = True
    DISCORD_WEBHOOK_URL: str = ""

    # ============================================================
    # LLM Provider API Keys
    # ============================================================
    GROQ_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    OPENROUTER_KEY: str = ""

    # ============================================================
    # LLM Model Assignments (provider:model)
    # ============================================================
    # Intake Agent
    INTAKE_AGENT_LLM: str = "groq:openai/gpt-oss-20b"
    INTAKE_AGENT_FALLBACK_1: str = "openrouter:nvidia/nemotron-3.5-lightning:free"
    INTAKE_AGENT_FALLBACK_2: str = "gemini:gemini-3.6-flash"

    # Injection Sanitizer Agent
    INJECTION_SANITIZER_AGENT_LLM: str = "gemini:gemini-3.6-flash"
    INJECTION_SANITIZER_AGENT_FALLBACK_1: str = "groq:openai/gpt-oss-20b"
    INJECTION_SANITIZER_AGENT_FALLBACK_2: str = "openrouter:nvidia/nemotron-3.5-lightning:free"

    # PII Scan Agent
    PII_SCAN_AGENT_LLM: str = "groq:openai/gpt-oss-20b"
    PII_SCAN_AGENT_FALLBACK_1: str = "gemini:gemini-3.6-flash"
    PII_SCAN_AGENT_FALLBACK_2: str = "openrouter:nvidia/nemotron-3.5-lightning:free"

    # EU AI Act Classification Agent
    EU_AI_ACT_CLASSIFIER_AGENT_LLM: str = "openrouter:nvidia/nemotron-3-ultra-550b-a55b:free"
    EU_AI_ACT_CLASSIFIER_AGENT_FALLBACK_1: str = "groq:openai/gpt-oss-120b"
    EU_AI_ACT_CLASSIFIER_AGENT_FALLBACK_2: str = "gemini:gemini-3.6-flash"

    # BaFin Compliance Agent
    BAFIN_COMPLIANCE_AGENT_LLM: str = "openrouter:nvidia/nemotron-3-ultra-550b-a55b:free"
    BAFIN_COMPLIANCE_AGENT_FALLBACK_1: str = "groq:openai/gpt-oss-120b"
    BAFIN_COMPLIANCE_AGENT_FALLBACK_2: str = "gemini:gemini-3.6-flash"

    # Translation Agent
    TRANSLATION_AGENT_LLM: str = "gemini:gemini-3.6-flash"
    TRANSLATION_AGENT_FALLBACK_1: str = "openrouter:nvidia/nemotron-3.5-lightning:free"
    TRANSLATION_AGENT_FALLBACK_2: str = "groq:openai/gpt-oss-20b"

    # Conflict Resolution Agent
    CONFLICT_RESOLUTION_AGENT_LLM: str = "gemini:gemini-3.6-flash"
    CONFLICT_RESOLUTION_AGENT_FALLBACK_1: str = "groq:openai/gpt-oss-20b"
    CONFLICT_RESOLUTION_AGENT_FALLBACK_2: str = "openrouter:nvidia/nemotron-3.5-lightning:free"

    # Clarification Agent
    CLARIFICATION_AGENT_LLM: str = "groq:openai/gpt-oss-20b"
    CLARIFICATION_AGENT_FALLBACK_1: str = "gemini:gemini-3.6-flash"
    CLARIFICATION_AGENT_FALLBACK_2: str = "openrouter:nvidia/nemotron-3.5-lightning:free"

    # Gap Assessment Agent
    GAP_ASSESSMENT_AGENT_LLM: str = "gemini:gemini-3.6-flash"
    GAP_ASSESSMENT_AGENT_FALLBACK_1: str = "openrouter:nvidia/nemotron-3.5-lightning:free"
    GAP_ASSESSMENT_AGENT_FALLBACK_2: str = "groq:openai/gpt-oss-20b"

    # Critic/QA Agent
    CRITIC_AGENT_LLM: str = "openrouter:nvidia/nemotron-3-ultra-550b-a55b:free"
    CRITIC_AGENT_FALLBACK_1: str = "groq:openai/gpt-oss-120b"
    CRITIC_AGENT_FALLBACK_2: str = "gemini:gemini-3.6-flash"

    # Report Agent
    REPORT_AGENT_LLM: str = "gemini:gemini-3.6-flash"
    REPORT_AGENT_FALLBACK_1: str = "groq:openai/gpt-oss-20b"
    REPORT_AGENT_FALLBACK_2: str = "openrouter:nvidia/nemotron-3.5-lightning:free"

    # ============================================================
    # Token / Context Budgets
    # ============================================================
    MAX_TOKENS_PER_AGENT_CALL: int = 1024
    MAX_TOOL_CALLS_PER_AGENT_RUN: int = 12
    DAILY_TOKEN_BUDGET: int = 100000
    LLM_ROUTER_MAX_CONTEXT_WARNING_PCT: float = 0.85

    # ============================================================
    # LangSmith / Observability
    # ============================================================
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "konformai"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""

    # ============================================================
    # Database
    # ============================================================
    DATABASE_URL: str = "postgresql+psycopg://user:pass@localhost:5432/konformai"
    PGVECTOR_COLLECTION: str = "konformai_kb"

    # ============================================================
    # Agent behavior
    # ============================================================
    MAX_CRITIC_RETRIES: int = 2
    CLASSIFICATION_CONFIDENCE_THRESHOLD: float = 0.6

    # ============================================================
    # Security
    # ============================================================
    API_AUTH_TOKEN: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:8501"

    # ============================================================
    # Paths
    # ============================================================
    KNOWLEDGE_BASE_DIR: str = "./knowledge_base"
    UPLOADED_DOCS_DIR: str = "./knowledge_base/uploaded"

    @property
    def cors_origins(self) -> List[str]:
        if not self.ALLOWED_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    def get_agent_model_chain(self, agent_name: str) -> List[str]:
        """Resolves the configured primary model and two fallbacks for any given agent name."""
        clean_name = agent_name.upper().strip()
        # Normalizes suffixes if needed (e.g. INTAKE -> INTAKE_AGENT)
        if not clean_name.endswith("_AGENT") and not clean_name.endswith("_CLASSIFIER"):
            normalized_name = f"{clean_name}_AGENT"
        else:
            normalized_name = clean_name

        primary_key = f"{normalized_name}_LLM"
        fallback_1_key = f"{normalized_name}_FALLBACK_1"
        fallback_2_key = f"{normalized_name}_FALLBACK_2"

        # Direct attribute access or fallback
        primary = getattr(self, primary_key, getattr(self, f"{clean_name}_LLM", "gemini:gemini-3.6-flash"))
        fb1 = getattr(self, fallback_1_key, getattr(self, f"{clean_name}_FALLBACK_1", "groq:openai/gpt-oss-20b"))
        fb2 = getattr(self, fallback_2_key, getattr(self, f"{clean_name}_FALLBACK_2", "openrouter:nvidia/nemotron-3.5-lightning:free"))

        return [primary, fb1, fb2]


settings = Settings()
