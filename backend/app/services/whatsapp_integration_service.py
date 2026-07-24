from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.repository import get_repository, utc_now
from app.services.audit_service import log_agent_run
from app.services.integration_utils import integration_store
from app.services.knowledge_graph_service import knowledge_graph
from app.services.secret_service import secret_service


GRAPH_BASE = "https://graph.facebook.com"
SYSTEM_WORKSPACE = "__kondai_system__"


def _workspace_token(workspace_id: str) -> str:
    return base64.urlsafe_b64encode(workspace_id.encode("utf-8")).decode("utf-8").rstrip("=")


def _workspace_from_token(token: str) -> str:
    padding = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(f"{token}{padding}".encode("utf-8")).decode("utf-8")


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:40]}"


def _parse_timestamp(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(str(value)), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return utc_now()


class WhatsAppIntegrationService:
    def __init__(self) -> None:
        self.repo = get_repository()
        self.settings = get_settings()

    def _connection(self, workspace_id: str) -> dict[str, Any] | None:
        return integration_store.get(workspace_id, "whatsapp")

    def status(self, workspace_id: str) -> dict[str, Any]:
        connection = self._connection(workspace_id)
        if not connection:
            return {
                "connected": False,
                "status": "not_connected",
                "provider": "meta_cloud_api",
                "display_phone_number": None,
                "verified_name": None,
                "phone_number_id": None,
                "waba_id": None,
                "callback_url": None,
                "last_synced_at": None,
                "summary": {},
                "onboarding_mode": "embedded_signup_v4",
                "webhook_configured": bool(
                    self.settings.meta_webhook_verify_token
                    and self.settings.meta_app_secret
                    and self.settings.public_api_base_url
                ),
            }
        return {
            "connected": connection.get("status") == "connected",
            "status": connection.get("status", "not_connected"),
            "provider": "meta_cloud_api",
            "display_phone_number": connection.get("display_phone_number"),
            "verified_name": connection.get("verified_name"),
            "quality_rating": connection.get("quality_rating"),
            "phone_number_id": connection.get("phone_number_id"),
            "waba_id": connection.get("waba_id"),
            "callback_url": connection.get("callback_url"),
            "last_synced_at": connection.get("last_synced_at"),
            "summary": connection.get("summary", {}),
            "subscription_warning": connection.get("subscription_warning", ""),
            "onboarding_mode": connection.get(
                "onboarding_mode", "embedded_signup_v4"
            ),
            "webhook_configured": bool(
                self.settings.meta_webhook_verify_token
                and self.settings.meta_app_secret
                and self.settings.public_api_base_url
            ),
        }

    def embedded_signup_config(self) -> dict[str, Any]:
        missing = []
        if not self.settings.meta_app_id:
            missing.append("META_APP_ID")
        if not self.settings.meta_app_secret:
            missing.append("META_APP_SECRET")
        if not self.settings.meta_embedded_signup_config_id:
            missing.append("META_EMBEDDED_SIGNUP_CONFIG_ID")
        if not self.settings.meta_webhook_verify_token:
            missing.append("META_WEBHOOK_VERIFY_TOKEN")
        if not self.settings.public_api_base_url:
            missing.append("PUBLIC_API_BASE_URL")
        return {
            "enabled": not missing,
            "app_id": self.settings.meta_app_id,
            "config_id": self.settings.meta_embedded_signup_config_id,
            "graph_version": self.settings.whatsapp_graph_version,
            "feature_type": self.settings.meta_embedded_signup_feature_type,
            "missing_configuration": missing,
            "webhook_callback_url": (
                f"{self.settings.public_api_base_url.rstrip('/')}"
                f"{self.settings.api_prefix}/integrations/whatsapp/webhook"
            ),
        }

    async def complete_embedded_signup(
        self,
        workspace_id: str,
        user_id: str,
        code: str,
        waba_id: str,
        phone_number_id: str,
        business_id: str = "",
        flow_type: str = "embedded_signup_v4",
    ) -> dict[str, Any]:
        config = self.embedded_signup_config()
        if not config["enabled"]:
            raise RuntimeError(
                "WhatsApp onboarding is not configured for this Kondai deployment. "
                f"Missing: {', '.join(config['missing_configuration'])}."
            )
        if not waba_id.isdigit() or not phone_number_id.isdigit():
            raise ValueError("Meta returned invalid WhatsApp account identifiers.")

        token_params = {
            "client_id": self.settings.meta_app_id,
            "client_secret": self.settings.meta_app_secret,
            "code": code,
        }
        if self.settings.meta_embedded_signup_redirect_uri:
            token_params["redirect_uri"] = (
                self.settings.meta_embedded_signup_redirect_uri
            )

        async with httpx.AsyncClient(timeout=40) as client:
            token_response = await client.get(
                f"{GRAPH_BASE}/{self.settings.whatsapp_graph_version}/oauth/access_token",
                params=token_params,
            )
            if token_response.status_code >= 400:
                raise ValueError(
                    "Meta could not complete WhatsApp signup: "
                    f"{self._meta_error(token_response)}"
                )
            token_payload = token_response.json()
            access_token = str(token_payload.get("access_token") or "")
            if not access_token:
                raise ValueError("Meta did not return a business access token.")

            phone_response = await client.get(
                f"{GRAPH_BASE}/{self.settings.whatsapp_graph_version}/{phone_number_id}",
                params={
                    "fields": (
                        "display_phone_number,verified_name,quality_rating,"
                        "code_verification_status,platform_type,account_mode"
                    ),
                    "access_token": access_token,
                },
            )
            if phone_response.status_code >= 400:
                raise ValueError(
                    "Meta returned a token, but Kondai could not verify the "
                    f"selected phone number: {self._meta_error(phone_response)}"
                )
            phone = phone_response.json()

            subscription = await client.post(
                f"{GRAPH_BASE}/{self.settings.whatsapp_graph_version}/{waba_id}/subscribed_apps",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if subscription.status_code >= 400:
                raise ValueError(
                    "WhatsApp signup finished, but Kondai could not subscribe to "
                    f"message webhooks: {self._meta_error(subscription)}"
                )

            registration_warning = ""
            two_step_pin = ""
            if self.settings.meta_auto_register_phone_number:
                two_step_pin = f"{secrets.randbelow(1_000_000):06d}"
                register = await client.post(
                    f"{GRAPH_BASE}/{self.settings.whatsapp_graph_version}/{phone_number_id}/register",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "pin": two_step_pin,
                    },
                )
                if register.status_code >= 400:
                    registration_warning = (
                        "The account is connected, but Meta did not confirm phone "
                        "registration automatically. The number may already be "
                        "registered or may require review in WhatsApp Manager. "
                        f"Meta response: {self._meta_error(register)}"
                    )

        connection = integration_store.save(
            workspace_id,
            "whatsapp",
            {
                "status": "connected",
                "connection_type": "embedded_signup_v4",
                "onboarding_mode": flow_type,
                "encrypted_access_token": secret_service.encrypt(access_token),
                "encrypted_two_step_pin": (
                    secret_service.encrypt(two_step_pin) if two_step_pin else ""
                ),
                "phone_number_id": phone_number_id,
                "waba_id": waba_id,
                "business_id": business_id,
                "display_phone_number": phone.get("display_phone_number"),
                "verified_name": phone.get("verified_name"),
                "quality_rating": phone.get("quality_rating"),
                "platform_type": phone.get("platform_type"),
                "account_mode": phone.get("account_mode"),
                "connected_by": user_id,
                "connected_at": utc_now(),
                "last_synced_at": None,
                "summary": {
                    "conversations": 0,
                    "inbound_messages": 0,
                    "unread_conversations": 0,
                    "open_tickets": 0,
                },
                "subscription_warning": registration_warning,
            },
        )
        self._save_route(workspace_id, "waba", waba_id)
        self._save_route(workspace_id, "phone", phone_number_id)
        log_agent_run(
            workspace_id,
            "integration_service",
            "whatsapp_embedded_signup_completed",
            (
                "Connected WhatsApp through Meta Embedded Signup and subscribed "
                "the selected account to Kondai webhooks."
            ),
            {"mode": "embedded_signup_v4", "provider": "meta"},
            {"waba_id": waba_id, "phone_number_id": phone_number_id},
            30,
        )
        return {**self.status(workspace_id), "registration_warning": registration_warning}

    def _route_id(self, route_type: str, external_id: str) -> str:
        return f"whatsapp-{route_type}-{external_id}"

    def _save_route(
        self, workspace_id: str, route_type: str, external_id: str
    ) -> None:
        record_id = self._route_id(route_type, external_id)
        current = self.repo.get(
            "integration_routes", record_id, SYSTEM_WORKSPACE
        )
        payload = {
            "id": record_id,
            "provider": "whatsapp",
            "route_type": route_type,
            "external_id": external_id,
            "target_workspace_id": workspace_id,
        }
        if current:
            self.repo.update(
                "integration_routes", record_id, SYSTEM_WORKSPACE, payload
            )
        else:
            self.repo.create(
                "integration_routes", SYSTEM_WORKSPACE, payload
            )

    def _workspace_for_event(
        self, waba_id: str = "", phone_number_id: str = ""
    ) -> str | None:
        for route_type, external_id in (
            ("phone", phone_number_id),
            ("waba", waba_id),
        ):
            if not external_id:
                continue
            route = self.repo.get(
                "integration_routes",
                self._route_id(route_type, external_id),
                SYSTEM_WORKSPACE,
            )
            if route and route.get("target_workspace_id"):
                return str(route["target_workspace_id"])
        return None

    def verify_global_webhook(
        self, mode: str, verify_token: str, challenge: str
    ) -> str:
        expected = self.settings.meta_webhook_verify_token
        if not expected:
            raise ValueError("META_WEBHOOK_VERIFY_TOKEN is not configured.")
        if mode != "subscribe" or not hmac.compare_digest(
            expected, verify_token
        ):
            raise ValueError("WhatsApp webhook verification failed.")
        return challenge

    def verify_global_signature(
        self, raw_body: bytes, signature_header: str
    ) -> None:
        if not self.settings.meta_app_secret:
            raise ValueError("META_APP_SECRET is not configured.")
        if not signature_header.startswith("sha256="):
            raise ValueError("Missing WhatsApp webhook signature.")
        expected = "sha256=" + hmac.new(
            self.settings.meta_app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature_header):
            raise ValueError("Invalid WhatsApp webhook signature.")

    def receive_global_webhook(
        self, raw_body: bytes, signature_header: str
    ) -> dict[str, int]:
        self.verify_global_signature(raw_body, signature_header)
        payload = json.loads(raw_body.decode("utf-8"))
        messages_created = 0
        statuses_updated = 0
        ignored_entries = 0
        for entry in payload.get("entry", []):
            waba_id = str(entry.get("id") or "")
            changes_by_workspace: dict[str, list[dict[str, Any]]] = {}
            for change in entry.get("changes", []):
                value = change.get("value") or {}
                metadata = value.get("metadata") or {}
                phone_number_id = str(
                    metadata.get("phone_number_id") or ""
                )
                workspace_id = self._workspace_for_event(
                    waba_id, phone_number_id
                )
                if not workspace_id:
                    ignored_entries += 1
                    continue
                changes_by_workspace.setdefault(workspace_id, []).append(change)
            for workspace_id, changes in changes_by_workspace.items():
                result = self._process_payload(
                    workspace_id,
                    {
                        "object": payload.get("object"),
                        "entry": [{"id": waba_id, "changes": changes}],
                    },
                )
                messages_created += result["messages_created"]
                statuses_updated += result["statuses_updated"]
        return {
            "messages_created": messages_created,
            "statuses_updated": statuses_updated,
            "ignored_entries": ignored_entries,
        }

    async def connect(
        self,
        workspace_id: str,
        user_id: str,
        access_token: str,
        phone_number_id: str,
        waba_id: str,
        app_secret: str,
        verify_token: str,
        webhook_base_url: str,
    ) -> dict[str, Any]:
        base_url = webhook_base_url.strip().rstrip("/")
        if urlparse(base_url).scheme != "https":
            raise ValueError(
                "Meta requires a public HTTPS webhook URL. Use your deployed API address "
                "or a secure tunnel such as ngrok during local development."
            )

        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.get(
                f"{GRAPH_BASE}/{self.settings.whatsapp_graph_version}/{phone_number_id}",
                params={
                    "fields": "display_phone_number,verified_name,quality_rating,code_verification_status,platform_type",
                    "access_token": access_token,
                },
            )
            if response.status_code >= 400:
                raise ValueError(
                    f"Meta could not verify the WhatsApp phone number: {self._meta_error(response)}"
                )
            phone = response.json()

            subscription_warning = ""
            subscribe = await client.post(
                f"{GRAPH_BASE}/{self.settings.whatsapp_graph_version}/{waba_id}/subscribed_apps",
                params={"access_token": access_token},
            )
            if subscribe.status_code >= 400:
                subscription_warning = (
                    "Kondai could not subscribe the app to the WABA automatically. Open Meta App "
                    "Dashboard → WhatsApp → Configuration and subscribe the messages field manually."
                )

        webhook_key = secrets.token_urlsafe(28)
        callback_url = (
            f"{base_url}{self.settings.api_prefix}/integrations/whatsapp/"
            f"webhook/{_workspace_token(workspace_id)}/{webhook_key}"
        )
        integration_store.save(
            workspace_id,
            "whatsapp",
            {
                "status": "connected",
                "connection_type": "meta_cloud_api",
                "encrypted_access_token": secret_service.encrypt(access_token),
                "encrypted_app_secret": secret_service.encrypt(app_secret),
                "encrypted_verify_token": secret_service.encrypt(verify_token),
                "phone_number_id": phone_number_id,
                "waba_id": waba_id,
                "webhook_key": webhook_key,
                "callback_url": callback_url,
                "display_phone_number": phone.get("display_phone_number"),
                "verified_name": phone.get("verified_name"),
                "quality_rating": phone.get("quality_rating"),
                "platform_type": phone.get("platform_type"),
                "connected_by": user_id,
                "connected_at": utc_now(),
                "last_synced_at": None,
                "summary": {
                    "conversations": 0,
                    "inbound_messages": 0,
                    "unread_conversations": 0,
                    "open_tickets": 0,
                },
                "subscription_warning": subscription_warning,
            },
        )
        log_agent_run(
            workspace_id,
            "integration_service",
            "whatsapp_connected",
            "Connected WhatsApp Business Platform and created a signed inbound webhook.",
            {"mode": "live_api", "provider": "meta_cloud_api"},
            {"phone_number_id": phone_number_id},
            20,
        )
        return self.status(workspace_id)

    def verify_webhook(
        self,
        workspace_token: str,
        webhook_key: str,
        mode: str,
        verify_token: str,
        challenge: str,
    ) -> str:
        workspace_id = _workspace_from_token(workspace_token)
        connection = self._connection(workspace_id)
        if not connection or connection.get("webhook_key") != webhook_key:
            raise ValueError("Unknown WhatsApp webhook.")
        stored = secret_service.decrypt(connection["encrypted_verify_token"])
        if mode != "subscribe" or not hmac.compare_digest(stored, verify_token):
            raise ValueError("WhatsApp webhook verification failed.")
        return challenge

    def verify_signature(self, workspace_id: str, raw_body: bytes, signature_header: str) -> None:
        connection = self._connection(workspace_id)
        if not connection:
            raise ValueError("WhatsApp is not connected.")
        if not signature_header.startswith("sha256="):
            raise ValueError("Missing WhatsApp webhook signature.")
        app_secret = secret_service.decrypt(connection["encrypted_app_secret"]).encode("utf-8")
        expected = "sha256=" + hmac.new(app_secret, raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature_header):
            raise ValueError("Invalid WhatsApp webhook signature.")

    def receive_webhook(
        self,
        workspace_token: str,
        webhook_key: str,
        raw_body: bytes,
        signature_header: str,
    ) -> dict[str, int]:
        workspace_id = _workspace_from_token(workspace_token)
        connection = self._connection(workspace_id)
        if not connection or connection.get("webhook_key") != webhook_key:
            raise ValueError("Unknown WhatsApp webhook.")
        self.verify_signature(workspace_id, raw_body, signature_header)
        payload = json.loads(raw_body.decode("utf-8"))
        return self._process_payload(workspace_id, payload)

    def _process_payload(
        self, workspace_id: str, payload: dict[str, Any]
    ) -> dict[str, int]:
        created = 0
        statuses = 0
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value") or {}
                contacts = {
                    str(item.get("wa_id")): (
                        (item.get("profile") or {}).get("name")
                        or str(item.get("wa_id"))
                    )
                    for item in value.get("contacts", [])
                    if item.get("wa_id")
                }
                for message in value.get("messages", []):
                    if self._store_inbound_message(
                        workspace_id, message, contacts
                    ):
                        created += 1
                for status_item in value.get("statuses", []):
                    if self._store_status(workspace_id, status_item):
                        statuses += 1
        if created:
            self.sync(workspace_id)
        return {"messages_created": created, "statuses_updated": statuses}

    def _store_inbound_message(
        self,
        workspace_id: str,
        message: dict[str, Any],
        contacts: dict[str, str],
    ) -> bool:
        external_id = str(message.get("id") or "")
        wa_id = str(message.get("from") or "")
        if not external_id or not wa_id:
            return False
        record_id = _stable_id("wa-message", external_id)
        if self.repo.get("whatsapp_messages", record_id, workspace_id):
            return False

        message_type = str(message.get("type") or "unknown")
        body, media_id = self._message_content(message)
        sent_at = _parse_timestamp(message.get("timestamp"))
        customer_name = contacts.get(wa_id, wa_id)
        conversation_id = _stable_id("wa-conversation", wa_id)
        self.repo.create(
            "whatsapp_messages",
            workspace_id,
            {
                "id": record_id,
                "external_message_id": external_id,
                "conversation_id": conversation_id,
                "direction": "inbound",
                "customer_phone": wa_id,
                "customer_name": customer_name,
                "message_type": message_type,
                "body": body,
                "media_id": media_id,
                "provider_timestamp": sent_at,
                "delivery_status": "received",
                "raw_context": message.get("context") or {},
            },
        )

        ticket = self._open_ticket(workspace_id, wa_id)
        if not ticket:
            ticket = self.repo.create(
                "support_tickets",
                workspace_id,
                {
                    "customer_name": customer_name,
                    "customer_email": f"{wa_id}@whatsapp.invalid",
                    "customer_phone": wa_id,
                    "channel": "whatsapp",
                    "subject": f"WhatsApp conversation with {customer_name}",
                    "message": body,
                    "priority": "medium",
                    "status": "open",
                    "assigned_agent": "support_agent",
                    "draft_status": "not_started",
                    "external_conversation_id": conversation_id,
                },
            )

        conversation = self.repo.get("whatsapp_conversations", conversation_id, workspace_id)
        if conversation:
            self.repo.update(
                "whatsapp_conversations",
                conversation_id,
                workspace_id,
                {
                    "customer_name": customer_name,
                    "last_message": body,
                    "last_message_type": message_type,
                    "last_message_at": sent_at,
                    "last_inbound_at": sent_at,
                    "unread_count": int(conversation.get("unread_count", 0)) + 1,
                    "message_count": int(conversation.get("message_count", 0)) + 1,
                    "ticket_id": ticket["id"],
                    "status": "open",
                },
            )
        else:
            self.repo.create(
                "whatsapp_conversations",
                workspace_id,
                {
                    "id": conversation_id,
                    "customer_phone": wa_id,
                    "customer_name": customer_name,
                    "last_message": body,
                    "last_message_type": message_type,
                    "last_message_at": sent_at,
                    "last_inbound_at": sent_at,
                    "unread_count": 1,
                    "message_count": 1,
                    "ticket_id": ticket["id"],
                    "status": "open",
                },
            )

        self.repo.update(
            "support_tickets",
            ticket["id"],
            workspace_id,
            {
                "message": self._transcript(workspace_id, conversation_id),
                "latest_message": body,
                "customer_name": customer_name,
                "status": "open" if ticket.get("status") == "resolved" else ticket.get("status", "open"),
                "draft_status": "not_started",
            },
        )
        self.repo.create(
            "feedback_items",
            workspace_id,
            {
                "ticket_id": ticket["id"],
                "external_message_id": external_id,
                "channel": "whatsapp",
                "type": "raw_customer_message",
                "content": body,
                "status": "unclassified",
            },
        )
        return True

    def _store_status(self, workspace_id: str, status_item: dict[str, Any]) -> bool:
        external_id = str(status_item.get("id") or "")
        if not external_id:
            return False
        record_id = _stable_id("wa-message", external_id)
        if not self.repo.get("whatsapp_messages", record_id, workspace_id):
            return False
        self.repo.update(
            "whatsapp_messages",
            record_id,
            workspace_id,
            {
                "delivery_status": status_item.get("status"),
                "delivery_timestamp": _parse_timestamp(status_item.get("timestamp")),
                "delivery_errors": status_item.get("errors") or [],
            },
        )
        return True

    @staticmethod
    def _message_content(message: dict[str, Any]) -> tuple[str, str | None]:
        message_type = str(message.get("type") or "unknown")
        payload = message.get(message_type) or {}
        media_id = payload.get("id") if isinstance(payload, dict) else None
        if message_type == "text":
            return str(payload.get("body") or ""), None
        if message_type == "button":
            return str(payload.get("text") or "[Button response]"), None
        if message_type == "interactive":
            reply = payload.get("button_reply") or payload.get("list_reply") or {}
            return str(reply.get("title") or reply.get("id") or "[Interactive response]"), None
        if message_type in {"image", "video", "document"}:
            caption = str(payload.get("caption") or "").strip()
            return caption or f"[{message_type.title()} received]", str(media_id) if media_id else None
        if message_type in {"audio", "voice", "sticker"}:
            return f"[{message_type.title()} received]", str(media_id) if media_id else None
        if message_type == "location":
            return (
                f"[Location: {payload.get('name') or ''} {payload.get('address') or ''} "
                f"{payload.get('latitude')},{payload.get('longitude')}]".replace("  ", " ").strip(),
                None,
            )
        if message_type == "reaction":
            return f"[Reaction: {payload.get('emoji') or ''}]", None
        if message_type == "contacts":
            return "[Contact card received]", None
        return f"[Unsupported WhatsApp message: {message_type}]", None

    def _open_ticket(self, workspace_id: str, wa_id: str) -> dict[str, Any] | None:
        return next(
            (
                ticket
                for ticket in self.repo.list("support_tickets", workspace_id)
                if ticket.get("channel") == "whatsapp"
                and ticket.get("customer_phone") == wa_id
                and ticket.get("status") in {"open", "escalated", "pending"}
            ),
            None,
        )

    def _transcript(self, workspace_id: str, conversation_id: str) -> str:
        messages = [
            item
            for item in self.repo.list("whatsapp_messages", workspace_id)
            if item.get("conversation_id") == conversation_id
        ]
        messages.sort(key=lambda item: item.get("provider_timestamp", item.get("created_at", "")))
        lines = []
        for item in messages[-20:]:
            speaker = item.get("customer_name") or "Customer" if item.get("direction") == "inbound" else "Business"
            lines.append(f"{speaker}: {item.get('body', '')}")
        return "\n".join(lines)

    def conversations(self, workspace_id: str) -> list[dict[str, Any]]:
        return self.repo.list("whatsapp_conversations", workspace_id)

    def messages(self, workspace_id: str, conversation_id: str) -> list[dict[str, Any]]:
        items = [
            item
            for item in self.repo.list("whatsapp_messages", workspace_id)
            if item.get("conversation_id") == conversation_id
        ]
        return sorted(items, key=lambda item: item.get("provider_timestamp", item.get("created_at", "")))

    def mark_read(self, workspace_id: str, conversation_id: str) -> dict[str, Any]:
        conversation = self.repo.get("whatsapp_conversations", conversation_id, workspace_id)
        if not conversation:
            raise ValueError("WhatsApp conversation not found.")
        return self.repo.update(
            "whatsapp_conversations", conversation_id, workspace_id, {"unread_count": 0}
        ) or conversation

    def sync(self, workspace_id: str) -> dict[str, Any]:
        connection = self._connection(workspace_id)
        if not connection:
            raise ValueError("WhatsApp is not connected.")
        conversations = self.conversations(workspace_id)
        messages = self.repo.list("whatsapp_messages", workspace_id)
        inbound = [item for item in messages if item.get("direction") == "inbound"]
        open_tickets = [
            item
            for item in self.repo.list("support_tickets", workspace_id)
            if item.get("channel") == "whatsapp" and item.get("status") in {"open", "escalated", "pending"}
        ]
        themes = self._themes(inbound)
        summary = {
            "conversations": len(conversations),
            "inbound_messages": len(inbound),
            "unread_conversations": sum(1 for item in conversations if int(item.get("unread_count", 0)) > 0),
            "open_tickets": len(open_tickets),
            "themes": themes,
        }
        integration_store.supersede_sources(workspace_id, "support", "whatsapp")
        knowledge_graph.ingest(
            workspace_id,
            "support",
            "WhatsApp customer conversations",
            {
                "open_tickets": len(open_tickets),
                "themes": themes,
                "messages_received": len(inbound),
                "conversations": len(conversations),
            },
            external_id="whatsapp",
            product_id=integration_store.product_id(workspace_id),
        )
        integration_store.save(
            workspace_id,
            "whatsapp",
            {**connection, "last_synced_at": utc_now(), "summary": summary},
        )
        return self.status(workspace_id)

    @staticmethod
    def _themes(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets = {
            "Billing and renewal": ("pay", "payment", "price", "renew", "subscription", "credit"),
            "Login and account": ("login", "password", "account", "sign in", "otp"),
            "Bug or error": ("error", "failed", "not working", "problem", "bug"),
            "Onboarding and guidance": ("how", "start", "help", "guide", "where"),
            "Feature request": ("can you add", "feature", "wish", "request"),
        }
        counts = {name: 0 for name in buckets}
        for item in messages:
            body = str(item.get("body") or "").lower()
            for name, keywords in buckets.items():
                if any(keyword in body for keyword in keywords):
                    counts[name] += 1
        return [{"name": name, "count": count} for name, count in counts.items() if count > 0]

    def send_text(self, workspace_id: str, conversation_id: str, text: str) -> dict[str, Any]:
        connection = self._connection(workspace_id)
        if not connection or connection.get("status") != "connected":
            raise ValueError("WhatsApp is not connected.")
        conversation = self.repo.get("whatsapp_conversations", conversation_id, workspace_id)
        if not conversation:
            raise ValueError("WhatsApp conversation not found.")
        last_inbound = str(conversation.get("last_inbound_at") or "")
        if not last_inbound:
            raise ValueError("A free-form reply requires a recent customer message.")
        try:
            last_inbound_at = datetime.fromisoformat(last_inbound)
        except ValueError as exc:
            raise ValueError("The conversation does not have a valid inbound timestamp.") from exc
        if datetime.now(timezone.utc) - last_inbound_at > timedelta(hours=self.settings.whatsapp_customer_window_hours):
            raise ValueError(
                "The WhatsApp customer-service window has closed. Use an approved message template to contact this customer."
            )
        body = text.strip()
        if not body:
            raise ValueError("WhatsApp reply cannot be empty.")
        if len(body) > self.settings.whatsapp_message_body_limit:
            raise ValueError(f"WhatsApp reply exceeds {self.settings.whatsapp_message_body_limit} characters.")

        access_token = secret_service.decrypt(connection["encrypted_access_token"])
        with httpx.Client(timeout=35) as client:
            response = client.post(
                f"{GRAPH_BASE}/{self.settings.whatsapp_graph_version}/{connection['phone_number_id']}/messages",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": conversation["customer_phone"],
                    "type": "text",
                    "text": {"preview_url": False, "body": body},
                },
            )
        if response.status_code >= 400:
            raise ValueError(f"WhatsApp could not send the message: {self._meta_error(response)}")
        result = response.json()
        external_id = str(((result.get("messages") or [{}])[0]).get("id") or secrets.token_urlsafe(16))
        record = self.repo.create(
            "whatsapp_messages",
            workspace_id,
            {
                "id": _stable_id("wa-message", external_id),
                "external_message_id": external_id,
                "conversation_id": conversation_id,
                "direction": "outbound",
                "customer_phone": conversation["customer_phone"],
                "customer_name": conversation.get("customer_name"),
                "message_type": "text",
                "body": body,
                "provider_timestamp": utc_now(),
                "delivery_status": "accepted",
            },
        )
        self.repo.update(
            "whatsapp_conversations",
            conversation_id,
            workspace_id,
            {
                "last_message": body,
                "last_message_type": "text",
                "last_message_at": utc_now(),
                "message_count": int(conversation.get("message_count", 0)) + 1,
            },
        )
        return record

    def disconnect(self, workspace_id: str) -> bool:
        connection = self._connection(workspace_id)
        if connection:
            for route_type, external_id in (
                ("waba", str(connection.get("waba_id") or "")),
                ("phone", str(connection.get("phone_number_id") or "")),
            ):
                if external_id:
                    self.repo.delete(
                        "integration_routes",
                        self._route_id(route_type, external_id),
                        SYSTEM_WORKSPACE,
                    )
        return integration_store.disconnect(workspace_id, "whatsapp")

    @staticmethod
    def _meta_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
            error = payload.get("error") or {}
            return str(error.get("error_user_msg") or error.get("message") or payload)
        except Exception:
            return response.text[:500] or f"HTTP {response.status_code}"


whatsapp_integration = WhatsAppIntegrationService()
