"""Token tracking, context window enforcement, and cost estimation."""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.db.models import LLMCallLog

logger = logging.getLogger(__name__)

# Approximate context limits for configured models
MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    # Groq / Open Source
    "openai/gpt-oss-20b": 32768,
    "openai/gpt-oss-120b": 32768,
    "llama-3.3-70b-versatile": 128000,
    "llama-3.1-8b-instant": 128000,
    # Gemini
    "gemini-3.6-flash": 1000000,
    "gemini-2.0-flash": 1000000,
    "gemini-1.5-flash": 1000000,
    "gemini-1.5-pro": 2000000,
    # OpenRouter Free Tiers
    "nvidia/nemotron-3.5-lightning:free": 32768,
    "nvidia/nemotron-3-ultra-550b-a55b:free": 128000,
    "meta-llama/llama-3.3-70b-instruct:free": 128000,
    # Default fallback
    "default": 32768,
}

# Pricing per 1k tokens in USD (Free tiers cost 0.0)
MODEL_PRICING_PER_1K: Dict[str, Tuple[float, float]] = {
    # (input_cost_per_1k, output_cost_per_1k)
    "openai/gpt-oss-20b": (0.0, 0.0),
    "openai/gpt-oss-120b": (0.0, 0.0),
    "gemini-3.6-flash": (0.0, 0.0),
    "gemini-2.0-flash": (0.0, 0.0),
    "gemini-1.5-flash": (0.000075, 0.0003),
    "nvidia/nemotron-3.5-lightning:free": (0.0, 0.0),
    "nvidia/nemotron-3-ultra-550b-a55b:free": (0.0, 0.0),
}


class ContextCheckResult(BaseModel):
    token_count: int
    context_limit: int
    is_warning: bool
    truncated_prompt: Optional[str] = None


class TokenTracker:
    """Manages token estimation, context window checking, budget accounting, and DB logging."""

    def __init__(self):
        self._cumulative_daily_tokens: int = 0
        self._last_reset_day: int = datetime.now(timezone.utc).day

    def _maybe_reset_daily_count(self):
        current_day = datetime.now(timezone.utc).day
        if current_day != self._last_reset_day:
            self._cumulative_daily_tokens = 0
            self._last_reset_day = current_day

    def estimate_tokens(self, text: str, model: str = "default") -> int:
        """Estimates token count using character heuristics (~4 chars/token)."""
        if not text:
            return 0
        # Fast rule of thumb: ~4 characters per token for European languages
        return max(1, len(text) // 4)

    def get_model_context_limit(self, model: str) -> int:
        """Looks up the known context window size for a given model string."""
        for key, limit in MODEL_CONTEXT_LIMITS.items():
            if key in model:
                return limit
        return MODEL_CONTEXT_LIMITS["default"]

    def check_context_window(
        self,
        prompt: str,
        model: str,
        retrieved_context: Optional[str] = None,
    ) -> ContextCheckResult:
        """Checks if assembled prompt approaches the model context window.

        If exceeding LLM_ROUTER_MAX_CONTEXT_WARNING_PCT (default 85%),
        gracefully truncates the retrieved context portion.
        """
        limit = self.get_model_context_limit(model)
        warning_threshold = int(limit * settings.LLM_ROUTER_MAX_CONTEXT_WARNING_PCT)

        total_tokens = self.estimate_tokens(prompt, model)
        is_warning = total_tokens >= warning_threshold

        truncated_prompt = None
        if is_warning:
            logger.warning(
                "Context window warning: Prompt token count %d exceeds %d%% of model '%s' limit (%d)",
                total_tokens,
                int(settings.LLM_ROUTER_MAX_CONTEXT_WARNING_PCT * 100),
                model,
                limit,
            )

            # If prompt contains retrieved context, truncate context portion
            if retrieved_context and len(retrieved_context) > 200:
                allowed_context_chars = max(500, int((warning_threshold - 500) * 4))
                truncated_ctx = (
                    retrieved_context[:allowed_context_chars]
                    + "\n... [Context truncated to fit model safety window] ..."
                )
                truncated_prompt = prompt.replace(retrieved_context, truncated_ctx)

        return ContextCheckResult(
            token_count=total_tokens,
            context_limit=limit,
            is_warning=is_warning,
            truncated_prompt=truncated_prompt,
        )

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculates estimated cost in USD based on provider pricing table."""
        if ":free" in model or "free" in model:
            return 0.0

        for key, (in_rate, out_rate) in MODEL_PRICING_PER_1K.items():
            if key in model:
                cost = (input_tokens / 1000.0 * in_rate) + (output_tokens / 1000.0 * out_rate)
                return round(cost, 6)

        return 0.0

    def record_usage(
        self,
        agent_name: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        failover_occurred: bool = False,
        failover_reason: Optional[str] = None,
        context_window_warning: bool = False,
        case_id: Optional[str] = None,
        db_session: Optional[Session] = None,
    ) -> LLMCallLog:
        """Records token usage, updates cumulative daily budget, and writes to llm_call_log table."""
        self._maybe_reset_daily_count()
        total_tokens = input_tokens + output_tokens
        self._cumulative_daily_tokens += total_tokens

        cost = self.estimate_cost(model, input_tokens, output_tokens)

        # Budget health check
        budget = settings.DAILY_TOKEN_BUDGET
        if self._cumulative_daily_tokens >= int(budget * 0.9):
            logger.warning(
                "Daily token budget near exhaustion: %d / %d tokens used (%.1f%%). Recommend model downgrade.",
                self._cumulative_daily_tokens,
                budget,
                (self._cumulative_daily_tokens / budget) * 100.0,
            )

        log_entry = LLMCallLog(
            case_id=case_id,
            agent_name=agent_name,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=cost,
            latency_ms=latency_ms,
            failover_occurred=failover_occurred,
            failover_reason=failover_reason,
            context_window_warning=context_window_warning,
            timestamp=datetime.now(timezone.utc),
        )

        if db_session is not None:
            try:
                db_session.add(log_entry)
                db_session.commit()
            except Exception as e:
                logger.error("Failed to persist LLMCallLog to database: %s", e)
                db_session.rollback()

        return log_entry

    def is_budget_near_exhaustion(self) -> bool:
        """Returns True if cumulative daily token consumption exceeds 90% of budget."""
        self._maybe_reset_daily_count()
        return self._cumulative_daily_tokens >= int(settings.DAILY_TOKEN_BUDGET * 0.9)


token_tracker = TokenTracker()
