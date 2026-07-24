from __future__ import annotations

import base64
import html
import json
import re
import secrets
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.repository import get_repository, utc_now
from app.services.audit_service import log_agent_run
from app.services.integration_utils import integration_store
from app.services.knowledge_graph_service import knowledge_graph
from app.services.secret_service import secret_service


GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1"


def _encode_workspace(workspace_id: str) -> str:
    return base64.urlsafe_b64encode(workspace_id.encode()).decode().rstrip("=")


def _decode_workspace(encoded: str) -> str:
    return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()


class GmailIntegrationService:
    provider = "gmail"

    def __init__(self) -> None:
        self.repo = get_repository()
        self.settings = get_settings()

    def start_oauth(self, workspace_id: str, user_id: str) -> dict[str, str]:
        if not self.settings.google_oauth_client_id:
            raise RuntimeError(
                "Google OAuth is not configured. Add GOOGLE_OAUTH_CLIENT_ID and "
                "GOOGLE_OAUTH_CLIENT_SECRET to backend/.env."
            )
        state = f"{_encode_workspace(workspace_id)}.{secrets.token_urlsafe(32)}"
        self.repo.create(
            "oauth_states",
            workspace_id,
            {
                "id": state,
                "provider": "gmail",
                "user_id": user_id,
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(minutes=10)
                ).isoformat(),
            },
        )
        query = urlencode(
            {
                "client_id": self.settings.google_oauth_client_id,
                "redirect_uri": self.settings.gmail_redirect_uri,
                "response_type": "code",
                "scope": self.settings.gmail_oauth_scope,
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "state": state,
            }
        )
        return {"authorization_url": f"{GOOGLE_AUTH}?{query}"}

    async def complete_oauth(self, code: str, state: str) -> str:
        try:
            workspace_id = _decode_workspace(state.split(".", 1)[0])
        except Exception as exc:
            raise ValueError("Invalid Google OAuth state.") from exc
        record = self.repo.get("oauth_states", state, workspace_id)
        if not record:
            raise ValueError("Google OAuth state was not found or already used.")
        if datetime.fromisoformat(record["expires_at"]) < datetime.now(timezone.utc):
            raise ValueError("Google OAuth state expired.")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GOOGLE_TOKEN,
                data={
                    "client_id": self.settings.google_oauth_client_id,
                    "client_secret": self.settings.google_oauth_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.settings.gmail_redirect_uri,
                },
            )
            if not response.is_success:
                raise ValueError(f"Google token exchange failed: {response.text}")
            tokens = response.json()
            profile = await client.get(
                f"{GMAIL_API}/users/me/profile",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            if not profile.is_success:
                raise ValueError(f"Gmail profile request failed: {profile.text}")
            profile_data = profile.json()

        existing = integration_store.get(workspace_id, self.provider) or {}
        refresh_token = tokens.get("refresh_token")
        if not refresh_token and existing.get("encrypted_tokens"):
            old = json.loads(secret_service.decrypt(existing["encrypted_tokens"]))
            refresh_token = old.get("refresh_token")
        token_record = {
            "access_token": tokens["access_token"],
            "refresh_token": refresh_token,
            "expires_at": (
                datetime.now(timezone.utc)
                + timedelta(seconds=int(tokens.get("expires_in", 3600)))
            ).isoformat(),
            "scope": tokens.get("scope", self.settings.gmail_oauth_scope),
            "token_type": tokens.get("token_type", "Bearer"),
        }
        integration_store.save(
            workspace_id,
            self.provider,
            {
                "status": "account_connected",
                "email_address": profile_data.get("emailAddress"),
                "messages_total": profile_data.get("messagesTotal"),
                "threads_total": profile_data.get("threadsTotal"),
                "encrypted_tokens": secret_service.encrypt(json.dumps(token_record)),
                "connected_by": record.get("user_id"),
                "connected_at": utc_now(),
                "last_synced_at": None,
            },
        )
        self.repo.delete("oauth_states", state, workspace_id)
        return workspace_id

    async def _access_token(self, workspace_id: str) -> tuple[str, dict[str, Any]]:
        connection = integration_store.get(workspace_id, self.provider)
        if not connection:
            raise ValueError("Gmail is not connected.")
        tokens = json.loads(secret_service.decrypt(connection["encrypted_tokens"]))
        expires_at = datetime.fromisoformat(tokens["expires_at"])
        if expires_at > datetime.now(timezone.utc) + timedelta(minutes=2):
            return tokens["access_token"], connection
        if not tokens.get("refresh_token"):
            raise ValueError("Gmail access expired. Reconnect the inbox.")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GOOGLE_TOKEN,
                data={
                    "client_id": self.settings.google_oauth_client_id,
                    "client_secret": self.settings.google_oauth_client_secret,
                    "refresh_token": tokens["refresh_token"],
                    "grant_type": "refresh_token",
                },
            )
        if not response.is_success:
            raise ValueError(f"Google token refresh failed: {response.text}")
        refreshed = response.json()
        tokens["access_token"] = refreshed["access_token"]
        tokens["expires_at"] = (
            datetime.now(timezone.utc)
            + timedelta(seconds=int(refreshed.get("expires_in", 3600)))
        ).isoformat()
        connection = integration_store.save(
            workspace_id,
            self.provider,
            {
                **connection,
                "encrypted_tokens": secret_service.encrypt(json.dumps(tokens)),
            },
        )
        return tokens["access_token"], connection

    @staticmethod
    def _headers(payload: dict[str, Any]) -> dict[str, str]:
        return {
            str(item.get("name", "")).lower(): str(item.get("value", ""))
            for item in payload.get("headers", [])
        }

    @staticmethod
    def _decode_body(payload: dict[str, Any]) -> str:
        candidates: list[str] = []

        def visit(part: dict[str, Any]) -> None:
            mime = part.get("mimeType", "")
            body = (part.get("body") or {}).get("data")
            if body and mime in {"text/plain", "text/html"}:
                try:
                    decoded = base64.urlsafe_b64decode(
                        body + "=" * (-len(body) % 4)
                    ).decode("utf-8", errors="replace")
                    candidates.append(decoded if mime == "text/plain" else re.sub(
                        r"<[^>]+>", " ", html.unescape(decoded)
                    ))
                except Exception:
                    pass
            for child in part.get("parts", []) or []:
                visit(child)

        visit(payload)
        text = next((item for item in candidates if item.strip()), "")
        return re.sub(r"\s+", " ", text).strip()[:12000]

    @staticmethod
    def _theme(subject: str, body: str) -> str:
        text = f"{subject} {body}".lower()
        if any(word in text for word in ("pay", "billing", "refund", "renew", "price")):
            return "Billing and renewal"
        if any(word in text for word in ("error", "bug", "failed", "not working", "crash")):
            return "Technical problem"
        if any(word in text for word in ("feature", "please add", "request", "would like")):
            return "Feature request"
        if any(word in text for word in ("start", "how do", "where", "guide", "onboard")):
            return "Onboarding and usage"
        return "General customer question"

    async def sync(
        self,
        workspace_id: str,
        query: str,
        max_messages: int,
    ) -> dict[str, Any]:
        access_token, connection = await self._access_token(workspace_id)
        query = query.strip() or self.settings.gmail_default_query
        max_messages = min(max_messages, self.settings.gmail_sync_limit, 500)
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=45) as client:
            listing = await client.get(
                f"{GMAIL_API}/users/me/messages",
                headers=headers,
                params={"q": query, "maxResults": max_messages},
            )
            if not listing.is_success:
                raise ValueError(f"Gmail message list failed: {listing.text}")
            message_refs = listing.json().get("messages", [])
            messages = []
            for ref in message_refs:
                response = await client.get(
                    f"{GMAIL_API}/users/me/messages/{ref['id']}",
                    headers=headers,
                    params={"format": "full"},
                )
                if response.is_success:
                    messages.append(response.json())

        existing_ids = {
            ticket.get("external_message_id")
            for ticket in self.repo.list("support_tickets", workspace_id)
            if ticket.get("external_message_id")
        }
        mailbox = str(connection.get("email_address") or "").lower()
        imported = 0
        themes: Counter[str] = Counter()
        for message in messages:
            payload = message.get("payload") or {}
            mail_headers = self._headers(payload)
            sender_name, sender_email = parseaddr(mail_headers.get("from", ""))
            sender_email = sender_email.lower()
            if not sender_email or sender_email == mailbox:
                continue
            subject = mail_headers.get("subject") or "Customer email"
            body = self._decode_body(payload) or message.get("snippet", "")
            theme = self._theme(subject, body)
            themes[theme] += 1
            if message.get("id") in existing_ids:
                continue
            ticket = self.repo.create(
                "support_tickets",
                workspace_id,
                {
                    "customer_name": sender_name or sender_email.split("@")[0],
                    "customer_email": sender_email,
                    "subject": subject[:200],
                    "message": body[:20000] or "Email body unavailable.",
                    "priority": "medium",
                    "status": "open",
                    "assigned_agent": "support_agent",
                    "draft_status": "not_started",
                    "source": "gmail",
                    "external_message_id": message.get("id"),
                    "external_thread_id": message.get("threadId"),
                },
            )
            self.repo.create(
                "feedback_items",
                workspace_id,
                {
                    "ticket_id": ticket["id"],
                    "type": "raw_customer_message",
                    "content": ticket["message"],
                    "status": "unclassified",
                    "source": "gmail",
                },
            )
            imported += 1

        open_gmail_tickets = [
            ticket for ticket in self.repo.list("support_tickets", workspace_id)
            if ticket.get("source") == "gmail"
            and ticket.get("status") in {"open", "escalated"}
        ]
        snapshot = {
            "provider": "gmail",
            "mailbox": connection.get("email_address"),
            "open_tickets": len(open_gmail_tickets),
            "messages_scanned": len(messages),
            "messages_imported": imported,
            "themes": [
                {"name": name, "count": count}
                for name, count in themes.most_common(10)
            ],
            "query": query,
            "synced_at": utc_now(),
        }
        integration_store.supersede_sources(workspace_id, "support", "gmail")
        knowledge_graph.ingest(
            workspace_id,
            "support",
            "Live support inbox — Gmail",
            snapshot,
            external_id="gmail",
            product_id=integration_store.product_id(workspace_id),
        )
        updated = integration_store.save(
            workspace_id,
            self.provider,
            {
                **connection,
                "status": "connected",
                "last_synced_at": snapshot["synced_at"],
                "query": query,
                "summary": snapshot,
            },
        )
        log_agent_run(
            workspace_id,
            "integration_service",
            "gmail_synced",
            f"Imported {imported} new customer email(s) from Gmail.",
            {"mode": "live_api", "provider": "gmail"},
            {},
            20,
        )
        return self.public_status(updated)

    def status(self, workspace_id: str) -> dict[str, Any]:
        return self.public_status(
            integration_store.get(workspace_id, self.provider)
        )

    @staticmethod
    def public_status(connection: dict[str, Any] | None) -> dict[str, Any]:
        if not connection:
            return {"status": "not_connected", "connected": False}
        return {
            "status": connection.get("status", "account_connected"),
            "connected": True,
            "email_address": connection.get("email_address"),
            "messages_total": connection.get("messages_total"),
            "threads_total": connection.get("threads_total"),
            "last_synced_at": connection.get("last_synced_at"),
            "query": connection.get("query"),
            "summary": connection.get("summary", {}),
        }

    def disconnect(self, workspace_id: str) -> bool:
        return integration_store.disconnect(workspace_id, self.provider)


gmail_integration = GmailIntegrationService()
