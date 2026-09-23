"""Unit tests for the multi-provider LLM router and token tracking."""

import pytest

from backend.core.config import settings
from backend.llm_router.providers import DryRunProvider, LLMResponse
from backend.llm_router.router import llm_router
from backend.llm_router.token_tracker import token_tracker


@pytest.mark.asyncio
async def test_dry_run_provider_returns_valid_response():
    """Verifies that DryRunProvider returns structured deterministic responses with 0 cost."""
    provider = DryRunProvider()
    messages = [{"role": "user", "content": "Test prompt for credit scoring intake"}]

    resp = await provider.complete(messages, model="dry-run-stub")
    assert isinstance(resp, LLMResponse)
    assert resp.provider == "dry_run"
    assert resp.input_tokens > 0
    assert resp.output_tokens > 0
    assert resp.latency_ms >= 0


def test_model_chain_resolution():
    """Verifies that settings properly resolves primary model and two fallbacks for any agent."""
    chain = settings.get_agent_model_chain("INTAKE_AGENT")
    assert len(chain) == 3
    assert "groq:" in chain[0] or "openai" in chain[0]

    critic_chain = settings.get_agent_model_chain("CRITIC_AGENT")
    assert len(critic_chain) == 3


def test_token_tracker_estimation():
    """Verifies token estimation heuristic."""
    text = "Artificial intelligence risk classification under EU AI Act Annex III."
    tokens = token_tracker.estimate_tokens(text)
    assert tokens > 5
    assert tokens < 50


def test_context_window_warning():
    """Verifies that prompts exceeding safety threshold trigger context warning."""
    huge_prompt = "regulatory compliance check " * 15000
    res = token_tracker.check_context_window(huge_prompt, model="openai/gpt-oss-20b")
    assert res.token_count > 10000
    assert res.is_warning is True


def test_tool_call_limiter():
    """Verifies enforcement of MAX_TOOL_CALLS_PER_AGENT_RUN to prevent runaway loops."""
    run_id = "test-agent-run-123"
    llm_router.reset_tool_call_counter(run_id)

    for _ in range(settings.MAX_TOOL_CALLS_PER_AGENT_RUN):
        allowed = llm_router.check_tool_call_limit(run_id)
        assert allowed is True

    # Next call should exceed limit and be rejected
    exceeded = llm_router.check_tool_call_limit(run_id)
    assert exceeded is False

    llm_router.reset_tool_call_counter(run_id)
