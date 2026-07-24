from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.core.config import get_settings


@dataclass
class EmailResult:
    accepted: bool
    provider: str
    provider_message_id: str
    status: str


class EmailService:
    async def send(self, recipient: str, subject: str, body: str) -> EmailResult:
        settings = get_settings()
        if settings.email_mode.lower() != "mock":
            raise RuntimeError(
                "No production email adapter is configured. Set EMAIL_MODE=mock "
                "or implement a verified provider adapter."
            )
        return EmailResult(
            accepted=True,
            provider="mock",
            provider_message_id=f"mock-{uuid4()}",
            status="accepted",
        )


email_service = EmailService()
