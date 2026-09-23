"""LLM Router managing per-agent model assignment and automatic fallback failover."""

import logging
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.llm_router.providers import (
    BaseLLMProvider,
    DryRunProvider,
    GeminiProvider,
    GroqProvider,
    LLMResponse,
    OpenRouterProvider,
)
from backend.llm_router.token_tracker import token_tracker

logger = logging.getLogger(__name__)


class LLMRouter:
    """Agent-agnostic router directing calls to primary and fallback LLM models."""

    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {
            "groq": GroqProvider(),
            "gemini": GeminiProvider(),
            "openrouter": OpenRouterProvider(),
            "dry_run": DryRunProvider(),
        }
        self.dry_run_provider = DryRunProvider()
        # Per-agent invocation tool call counters
        self._tool_call_counters: Dict[str, int] = {}

    def parse_provider_spec(self, spec: str) -> Tuple[str, str]:
        """Parses 'provider:model' string, e.g. 'groq:openai/gpt-oss-20b'."""
        if ":" in spec:
            parts = spec.split(":", 1)
            return parts[0].strip().lower(), parts[1].strip()
        # Default fallback if provider prefix omitted
        return "gemini", spec.strip()

    def get_provider_client(self, provider_name: str) -> BaseLLMProvider:
        """Returns the client wrapper for a given provider name."""
        return self._providers.get(provider_name, self.dry_run_provider)

    def check_tool_call_limit(self, agent_run_id: str) -> bool:
        """Enforces MAX_TOOL_CALLS_PER_AGENT_RUN hard cap per agent invocation."""
        current_count = self._tool_call_counters.get(agent_run_id, 0)
        if current_count >= settings.MAX_TOOL_CALLS_PER_AGENT_RUN:
            logger.warning(
                "Runaway tool loop prevented: Agent run '%s' reached tool call limit (%d)",
                agent_run_id,
                settings.MAX_TOOL_CALLS_PER_AGENT_RUN,
            )
            return False
        self._tool_call_counters[agent_run_id] = current_count + 1
        return True

    def reset_tool_call_counter(self, agent_run_id: str) -> None:
        """Resets the tool call counter when an agent run finishes."""
        self._tool_call_counters.pop(agent_run_id, None)

    async def complete(
        self,
        agent_name: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.1,
        case_id: Optional[str] = None,
        db_session: Optional[Session] = None,
        retrieved_context: Optional[str] = None,
    ) -> LLMResponse:
        """Executes LLM completion for an agent across its configured fallback chain.

        1. Checks GLOBAL_DRY_RUN switch -> returns deterministic mock instantly.
        2. Inspects context-window token limits and applies graceful truncation.
        3. Attempts primary model -> fallback 1 -> fallback 2.
        4. Logs every failover event and token usage.
        """
        # Hard cap on output tokens per single call
        effective_max_tokens = min(
            max_tokens or settings.MAX_TOKENS_PER_AGENT_CALL,
            settings.MAX_TOKENS_PER_AGENT_CALL,
        )

        # 1. Global Dry-Run switch
        if settings.GLOBAL_DRY_RUN:
            logger.info("GLOBAL_DRY_RUN enabled: Routing '%s' to DryRunProvider", agent_name)
            response = await self.dry_run_provider.complete(
                messages=messages,
                model="dry-run-stub",
                max_tokens=effective_max_tokens,
                temperature=temperature,
            )
            token_tracker.record_usage(
                agent_name=agent_name,
                provider="dry_run",
                model="dry-run-stub",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=response.latency_ms,
                case_id=case_id,
                db_session=db_session,
            )
            return response

        # 2. Retrieve model chain from settings
        model_chain = settings.get_agent_model_chain(agent_name)

        # Budget exhaustion check: if budget is low, prioritize free models
        if token_tracker.is_budget_near_exhaustion():
            logger.warning(
                "Daily token budget nearing exhaustion. Demoting agent '%s' to free fallback.",
                agent_name,
            )
            # Reorder chain to prioritize free openrouter model if available
            model_chain = sorted(
                model_chain,
                key=lambda m: 0 if "free" in m.lower() else 1,
            )

        # 3. Context window check on combined prompt
        prompt_text = "\n".join([m.get("content", "") for m in messages])
        context_check = token_tracker.check_context_window(
            prompt=prompt_text,
            model=model_chain[0],
            retrieved_context=retrieved_context,
        )

        # If prompt was truncated to stay within context margin, update last message
        effective_messages = messages
        if context_check.truncated_prompt and messages:
            effective_messages = list(messages)
            effective_messages[-1] = {
                "role": messages[-1].get("role", "user"),
                "content": context_check.truncated_prompt,
            }

        # 4. Attempt model chain execution with automatic failover
        errors: List[str] = []
        failover_occurred = False
        failover_reason: Optional[str] = None

        for idx, model_spec in enumerate(model_chain):
            provider_name, model_name = self.parse_provider_spec(model_spec)
            provider = self.get_provider_client(provider_name)

            if idx > 0:
                failover_occurred = True
                failover_reason = f"Failover #{idx} to {provider_name}:{model_name} due to prior error: {errors[-1]}"
                logger.warning(
                    "Agent '%s': %s",
                    agent_name,
                    failover_reason,
                )

            try:
                response = await provider.complete(
                    messages=effective_messages,
                    model=model_name,
                    max_tokens=effective_max_tokens,
                    temperature=temperature,
                )

                # Record token metrics and DB audit
                token_tracker.record_usage(
                    agent_name=agent_name,
                    provider=provider_name,
                    model=model_name,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    latency_ms=response.latency_ms,
                    failover_occurred=failover_occurred,
                    failover_reason=failover_reason,
                    context_window_warning=context_check.is_warning,
                    case_id=case_id,
                    db_session=db_session,
                )

                return response

            except Exception as exc:
                err_msg = f"Provider '{provider_name}' model '{model_name}' failed: {str(exc)}"
                logger.error("Agent '%s' attempt %d failed: %s", agent_name, idx + 1, err_msg)
                errors.append(err_msg)

        # 5. Final fallback to DryRunProvider if all configured providers fail
        logger.critical(
            "Agent '%s': All configured models failed in fallback chain (%s). Returning dry-run fallback.",
            agent_name,
            "; ".join(errors),
        )

        dry_run_resp = await self.dry_run_provider.complete(
            messages=effective_messages,
            model="emergency-dry-run-fallback",
            max_tokens=effective_max_tokens,
            temperature=temperature,
        )

        token_tracker.record_usage(
            agent_name=agent_name,
            provider="dry_run",
            model="emergency-dry-run-fallback",
            input_tokens=dry_run_resp.input_tokens,
            output_tokens=dry_run_resp.output_tokens,
            latency_ms=dry_run_resp.latency_ms,
            failover_occurred=True,
            failover_reason="All primary and fallback LLM providers failed: " + " | ".join(errors),
            context_window_warning=context_check.is_warning,
            case_id=case_id,
            db_session=db_session,
        )

        return dry_run_resp


llm_router = LLMRouter()
