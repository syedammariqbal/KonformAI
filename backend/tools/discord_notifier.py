"""Discord webhook notifier for human review alerts and prompt injection halts."""

import logging
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from backend.core.config import settings

logger = logging.getLogger(__name__)


class DiscordAlert(BaseModel):
    """Input payload schema for sending alerts to Discord."""

    title: str = Field(..., description="Short headline for the alert")
    severity: str = Field(default="INFO", description="Severity level: INFO, WARNING, HIGH_RISK, CRITICAL, PROHIBITED, INJECTION")
    summary: str = Field(..., description="Concise explanation of what occurred and what action is required")
    case_id: Optional[str] = Field(default=None, description="UUID of the affected evaluation case")
    review_url: Optional[str] = Field(default=None, description="Direct URL link to the human review UI")


class DiscordResult(BaseModel):
    """Execution status returned by the Discord notifier."""

    success: bool
    status_code: Optional[int] = None
    skipped: bool = False
    error: Optional[str] = None


class DiscordNotifier:
    """Sends rich embed notifications to a configured Discord webhook channel."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.DISCORD_WEBHOOK_URL

    def _get_color_for_severity(self, severity: str) -> int:
        sev = severity.upper()
        if sev in ["CRITICAL", "PROHIBITED", "INJECTION", "ERROR"]:
            return 0xE74C3C  # Red
        if sev in ["HIGH", "HIGH_RISK", "WARNING"]:
            return 0xE67E22  # Orange
        if sev in ["APPROVED", "SUCCESS"]:
            return 0x2ECC71  # Green
        return 0x3498DB  # Blue

    async def send_alert(self, alert: DiscordAlert) -> DiscordResult:
        """Dispatches an alert to the Discord webhook if configured."""
        if not settings.ENABLE_NOTIFICATIONS:
            logger.info("Discord notification skipped: ENABLE_NOTIFICATIONS is disabled.")
            return DiscordResult(success=True, skipped=True)

        url = self.webhook_url or settings.DISCORD_WEBHOOK_URL
        if not url:
            logger.info("Discord notification skipped: DISCORD_WEBHOOK_URL is not set.")
            return DiscordResult(success=True, skipped=True)

        color = self._get_color_for_severity(alert.severity)

        embed_fields = [
            {"name": "Severity", "value": f"`{alert.severity.upper()}`", "inline": True},
        ]
        if alert.case_id:
            embed_fields.append({"name": "Case ID", "value": f"`{alert.case_id}`", "inline": True})

        description = alert.summary
        if alert.review_url:
            description += f"\n\n**Action Required:** [Open Compliance Review Portal]({alert.review_url})"

        payload = {
            "username": "KonformAI Regulatory Guardian",
            "avatar_url": "https://raw.githubusercontent.com/KonformAI/assets/main/shield.png",
            "embeds": [
                {
                    "title": f"🛡️ {alert.title}",
                    "description": description,
                    "color": color,
                    "fields": embed_fields,
                    "footer": {"text": "KonformAI Multi-Agent Compliance System"},
                }
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code in [200, 204]:
                    logger.info("Discord alert delivered: %s", alert.title)
                    return DiscordResult(success=True, status_code=resp.status_code)
                else:
                    err = f"Discord webhook returned HTTP {resp.status_code}: {resp.text}"
                    logger.error(err)
                    return DiscordResult(success=False, status_code=resp.status_code, error=err)
        except Exception as exc:
            err = f"Failed to send Discord alert: {str(exc)}"
            logger.error(err)
            return DiscordResult(success=False, error=err)


discord_notifier = DiscordNotifier()
