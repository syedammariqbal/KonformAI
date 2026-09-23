"""Provider abstractions for multi-LLM routing (Groq, Gemini, OpenRouter, DryRun).

Exposes a uniform complete(messages, model, max_tokens, temperature) interface.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel

from backend.core.config import settings

logger = logging.getLogger(__name__)


class LLMResponse(BaseModel):
    """Uniform output schema across all LLM providers."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str
    latency_ms: float
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Sends chat messages to the model provider and returns a standard LLMResponse."""
        pass


class GroqProvider(BaseLLMProvider):
    """Groq API client wrapper (OpenAI-compatible chat completions)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.base_url, headers=headers, json=payload)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Groq API error {resp.status_code}: {resp.text}"
                )

            data = resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})

            return LLMResponse(
                content=choice["message"]["content"] or "",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                model=model,
                provider="groq",
                latency_ms=round(latency_ms, 2),
                raw_response=data,
            )


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter API client wrapper (OpenAI-compatible chat completions)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENROUTER_KEY
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("OPENROUTER_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/KonformAI",
            "X-Title": "KonformAI Compliance Agent",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(self.base_url, headers=headers, json=payload)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code != 200:
                raise RuntimeError(
                    f"OpenRouter API error {resp.status_code}: {resp.text}"
                )

            data = resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})

            return LLMResponse(
                content=choice["message"]["content"] or "",
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                model=model,
                provider="openrouter",
                latency_ms=round(latency_ms, 2),
                raw_response=data,
            )


class GeminiProvider(BaseLLMProvider):
    """Google Gemini REST client wrapper."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY is not configured")

        # Pass through the model string as-is; only default if empty
        clean_model = model.strip() if model else ""
        if not clean_model:
            clean_model = "gemini-2.0-flash"

        url = f"{self.base_url}/{clean_model}:generateContent?key={self.api_key}"

        # Convert messages to Gemini contents format
        contents = []
        for m in messages:
            role = "user" if m.get("role") in ["user", "system"] else "model"
            contents.append({
                "role": role,
                "parts": [{"text": m.get("content", "")}],
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            }
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Gemini API error {resp.status_code}: {resp.text}"
                )

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini returned empty candidate list")

            text = ""
            parts = candidates[0].get("content", {}).get("parts", [])
            for p in parts:
                text += p.get("text", "")

            usage = data.get("usageMetadata", {})

            return LLMResponse(
                content=text,
                input_tokens=usage.get("promptTokenCount", 0),
                output_tokens=usage.get("candidatesTokenCount", 0),
                model=clean_model,
                provider="gemini",
                latency_ms=round(latency_ms, 2),
                raw_response=data,
            )


class DryRunProvider(BaseLLMProvider):
    """Deterministic stub provider for testing, evaluation, and zero-cost demos."""

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> LLMResponse:
        # Inspect prompt to return contextually appropriate deterministic mock JSON/text
        last_content = messages[-1]["content"].lower() if messages else ""

        if "normalize" in last_content or "intake" in last_content or "system purpose" in last_content:
            mock_content = json.dumps({
                "system_purpose": "AI credit scoring engine evaluating SME loan creditworthiness",
                "data_types_used": ["bank transaction history", "financial statements", "tax filings"],
                "decision_autonomy_level": "semi-automated with human approval above 50,000 EUR",
                "affected_persons": "SME business owners and loan applicants",
                "deployment_context": "Production banking environment in Germany",
                "sector": "Banking / Financial Services"
            }, indent=2)
        elif "injection" in last_content or "sanitizer" in last_content:
            mock_content = json.dumps({
                "is_injection": False,
                "confidence": 0.99,
                "explanation": "Dry-run check: text contains legitimate domain descriptions without jailbreak or prompt override syntax."
            }, indent=2)
        elif "eu ai act" in last_content or "classifier" in last_content:
            # Check for Article 5 keywords in prompt
            if "social scoring" in last_content or "biometric" in last_content or "subliminal" in last_content:
                mock_content = json.dumps({
                    "risk_tier": "prohibited",
                    "is_prohibited": True,
                    "cited_articles": ["Article 5(1)(c) - Social scoring for general purposes by public or private actors"],
                    "confidence_score": 0.95,
                    "reasoning": "The system monitors natural persons to assign general trust scores leading to detrimental treatment outside the original context."
                }, indent=2)
            else:
                mock_content = json.dumps({
                    "risk_tier": "high",
                    "is_prohibited": False,
                    "cited_articles": ["Article 6(2)", "Annex III Point 5(b) - AI systems intended to be used to evaluate the creditworthiness of natural persons or establish their credit score"],
                    "confidence_score": 0.92,
                    "reasoning": "Under Annex III Point 5(b), AI systems intended for evaluating creditworthiness or credit scoring in financial services are classified as High-Risk."
                }, indent=2)
        elif "bafin" in last_content or "marisk" in last_content:
            mock_content = json.dumps({
                "applicable_obligations": [
                    {
                        "source": "MaRisk AT 4.3.2 (Tz. 1)",
                        "obligation": "Model risk management for credit-decision models: documented validation, backtesting, and governance controls.",
                        "language": "de"
                    },
                    {
                        "source": "BaFin BDAI Principles 2021 (Principle 3 & 4)",
                        "obligation": "Explainability and traceability of automated decision algorithms in loan approval.",
                        "language": "en"
                    },
                    {
                        "source": "KWG § 25a Abs. 1",
                        "obligation": "Adequate internal risk-management mechanisms and proper business organization.",
                        "language": "de"
                    }
                ],
                "confidence_score": 0.90
            }, indent=2)
        elif "translate" in last_content:
            mock_content = json.dumps({
                "translations": [
                    {
                        "source_id": "MaRisk AT 4.3.2",
                        "original_de": "Die Institute müssen angemessene Verfahren zur Identifizierung, Beurteilung, Steuerung sowie Überwachung und Kommunikation der Modellrisiken einrichten.",
                        "english_translation": "Institutions must establish adequate procedures for identifying, assessing, managing, monitoring, and communicating model risks.",
                        "disclaimer": "This English version is provided for information purposes only. The original German text is binding in all respects."
                    }
                ]
            }, indent=2)
        elif "gap" in last_content:
            mock_content = json.dumps({
                "gaps": [
                    {
                        "id": "GAP-01",
                        "control_area": "Human Oversight (EU AI Act Art. 14)",
                        "severity": "HIGH",
                        "missing_control": "No documented emergency intervention mechanism for credit officers to override automated scoring.",
                        "remediation": "Implement an explicit override interface in the credit approval workflow."
                    },
                    {
                        "id": "GAP-02",
                        "control_area": "Model Validation (MaRisk AT 4.3.2)",
                        "severity": "MEDIUM",
                        "missing_control": "Quarterly model drift and backtesting reports are not formalized in policy.",
                        "remediation": "Establish a formalized model validation calendar with independent risk control sign-off."
                    }
                ]
            }, indent=2)
        elif "critic" in last_content:
            mock_content = json.dumps({
                "verdict": "APPROVED",
                "revision_target": None,
                "issues": [],
                "grounding_check": "All cited statutory articles (Annex III 5(b), MaRisk AT 4.3.2, KWG § 25a) verified against ingested knowledge base passages."
            }, indent=2)
        elif "report" in last_content:
            mock_content = """# KonformAI Executive Compliance Assessment Report

**System Evaluated:** AI Credit-Scoring Engine for SME Loans
**Date:** 2026-09-16
**Status:** High-Risk System (EU AI Act & BaFin Regulated)

## 1. Executive Summary
The submitted AI credit-scoring engine is classified as **High-Risk** under Annex III Point 5(b) of the EU AI Act (Regulation (EU) 2024/1689). Additionally, German federal banking requirements under **KWG § 25a** and **MaRisk AT 4.3.2** impose mandatory model risk management and governance obligations.

## 2. EU AI Act Classification
- **Risk Tier:** High-Risk
- **Legal Grounds:** Article 6(2) in conjunction with Annex III, Point 5(b).
- **Core Obligations:**
  - Risk Management System (Article 9)
  - Data Governance and Data Quality (Article 10)
  - Technical Documentation and Record Keeping (Articles 11 & 12)
  - Human Oversight Measures (Article 14)
  - Accuracy, Robustness, and Cybersecurity (Article 15)

## 3. German BaFin & Federal Supervisory Obligations
- **MaRisk AT 4.3.2 (Model Risk Management):** Documented validation, independent model review, backtesting, and sensitivity analysis.
- **KWG § 25a:** Proper business organization and risk management.
- **BaFin BDAI Principles (2021):** Algorithmic explainability and fairness in customer-facing credit decisions.

## 4. Gap Analysis & Remediation Roadmap
1. **[HIGH] Human Oversight Mechanism:** Implement a formal override and stop-switch interface for credit officers.
2. **[MEDIUM] Model Drift Monitoring:** Establish quarterly backtesting schedules as mandated by MaRisk AT 4.3.2.

---
*Notice: This report is generated by an automated compliance-support tool and does not constitute formal legal advice. Citations from German statutory texts (KWG, WpHG, MaRisk) are provided with English renderings for convenience only; the German original remains the sole authoritative legal text.*
"""
        else:
            mock_content = "KonformAI Dry-Run Response: The operation completed successfully with zero simulated errors."

        return LLMResponse(
            content=mock_content,
            input_tokens=150,
            output_tokens=300,
            model=model,
            provider="dry_run",
            latency_ms=15.0,
        )
