"""Microsoft Presidio PII detection and redaction tool wrapper."""

import logging
import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PIIEntity(BaseModel):
    """Details of a single identified PII occurrence."""

    entity_type: str
    start: int
    end: int
    score: float
    text_sample: Optional[str] = None


class PIIScanRequest(BaseModel):
    """Input parameters for PII analysis."""

    text: str = Field(..., description="Document content to inspect for sensitive PII")
    language: str = Field(default="en", description="Language code ('en' or 'de')")
    entities: Optional[List[str]] = Field(
        default=None,
        description="List of entities to detect (e.g. ['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'IBAN_CODE'])",
    )
    action: Literal["detect", "redact"] = Field(
        default="detect",
        description="Whether to only detect entities or also return redacted text",
    )


class PIIScanResult(BaseModel):
    """Structured response detailing detected sensitive entities."""

    entity_count: int
    entities_found: List[PIIEntity]
    redacted_text: Optional[str] = None
    scanned_language: str = "en"
    has_high_risk_pii: bool = False


class PresidioTool:
    """Encapsulates Presidio AnalyzerEngine and AnonymizerEngine with regex fallback."""

    def __init__(self):
        self._analyzer = None
        self._anonymizer = None
        self._init_attempted = False

    def _init_engines(self):
        if self._init_attempted:
            return
        self._init_attempted = True
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine

            self._analyzer = AnalyzerEngine()
            self._anonymizer = AnonymizerEngine()
            logger.info("Microsoft Presidio engines initialized successfully.")
        except Exception as e:
            logger.warning("Microsoft Presidio full NLP backend unavailable (%s); using regex fallback.", e)
            self._analyzer = None
            self._anonymizer = None

    def _regex_scan(self, text: str, action: str) -> PIIScanResult:
        """Lightweight regex-based fallback for email, phone, IBAN, and credit cards."""
        entities: List[PIIEntity] = []
        redacted = text

        patterns = [
            ("EMAIL_ADDRESS", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", 0.95),
            ("PHONE_NUMBER", r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b", 0.85),
            ("IBAN_CODE", r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", 0.95),
            ("CREDIT_CARD", r"\b(?:\d{4}[-\s]?){3}\d{4}\b", 0.90),
        ]

        for ent_type, regex_str, score in patterns:
            for match in re.finditer(regex_str, text):
                matched_str = match.group(0)
                entities.append(
                    PIIEntity(
                        entity_type=ent_type,
                        start=match.start(),
                        end=match.end(),
                        score=score,
                        text_sample=matched_str[:4] + "***" if len(matched_str) > 4 else "***",
                    )
                )

        if action == "redact":
            for ent in sorted(entities, key=lambda e: e.start, reverse=True):
                redacted = (
                    redacted[: ent.start]
                    + f"<{ent.entity_type}_REDACTED>"
                    + redacted[ent.end :]
                )

        has_high_risk = any(e.entity_type in ["IBAN_CODE", "CREDIT_CARD"] for e in entities)
        return PIIScanResult(
            entity_count=len(entities),
            entities_found=entities,
            redacted_text=redacted if action == "redact" else None,
            has_high_risk_pii=has_high_risk,
        )

    def scan(self, request: PIIScanRequest) -> PIIScanResult:
        """Scans the text for PII entities and applies redaction if requested."""
        self._init_engines()

        if self._analyzer is None:
            return self._regex_scan(request.text, request.action)

        try:
            # Full Presidio scan
            lang = "en" if request.language != "de" else "en"  # Default to en model if de spaCy isn't installed
            results = self._analyzer.analyze(
                text=request.text,
                entities=request.entities,
                language=lang,
                score_threshold=0.5,
            )

            entities: List[PIIEntity] = []
            for res in results:
                sample = request.text[res.start:res.end]
                masked_sample = sample[:3] + "***" if len(sample) > 3 else "***"
                entities.append(
                    PIIEntity(
                        entity_type=res.entity_type,
                        start=res.start,
                        end=res.end,
                        score=round(res.score, 2),
                        text_sample=masked_sample,
                    )
                )

            redacted_text = None
            if request.action == "redact":
                from presidio_anonymizer.entities import OperatorConfig

                operators = {
                    "DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED_PII>"}),
                    "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<REDACTED_EMAIL>"}),
                    "IBAN_CODE": OperatorConfig("replace", {"new_value": "<REDACTED_IBAN>"}),
                    "PERSON": OperatorConfig("replace", {"new_value": "<REDACTED_NAME>"}),
                }
                anonymized = self._anonymizer.anonymize(
                    text=request.text,
                    analyzer_results=results,
                    operators=operators,
                )
                redacted_text = anonymized.text

            has_high_risk = any(
                e.entity_type in ["IBAN_CODE", "CREDIT_CARD", "US_SSN", "MEDICAL_LICENSE"]
                for e in entities
            )

            return PIIScanResult(
                entity_count=len(entities),
                entities_found=entities,
                redacted_text=redacted_text,
                scanned_language=request.language,
                has_high_risk_pii=has_high_risk,
            )

        except Exception as e:
            logger.warning("Presidio analyzer encountered error (%s); falling back to regex.", e)
            return self._regex_scan(request.text, request.action)


presidio_tool = PresidioTool()
