from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.repository import utc_now
from app.services.audit_service import log_agent_run
from app.services.integration_utils import integration_store
from app.services.knowledge_graph_service import knowledge_graph
from app.services.secret_service import secret_service


STRIPE_API = "https://api.stripe.com/v1"


class StripeIntegrationService:
    provider = "stripe"

    @staticmethod
    def _headers(secret_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {secret_key}"}

    async def _list_all(
        self,
        client: httpx.AsyncClient,
        path: str,
        secret_key: str,
        params: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        starting_after: str | None = None
        for _ in range(get_settings().stripe_sync_page_limit):
            request_params = list(params) + [("limit", "100")]
            if starting_after:
                request_params.append(("starting_after", starting_after))
            response = await client.get(
                f"{STRIPE_API}/{path}",
                headers=self._headers(secret_key),
                params=request_params,
            )
            self._raise(response)
            payload = response.json()
            data = payload.get("data", [])
            output.extend(data)
            if not payload.get("has_more") or not data:
                break
            starting_after = data[-1].get("id")
        return output

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            message = response.json().get("error", {}).get("message")
        except Exception:
            message = response.text
        raise ValueError(message or f"Stripe returned {response.status_code}.")

    @staticmethod
    def monthly_value(subscription: dict[str, Any]) -> float:
        total = 0.0
        for item in (subscription.get("items") or {}).get("data", []):
            price = item.get("price") or {}
            recurring = price.get("recurring") or {}
            amount = float(price.get("unit_amount") or 0)
            quantity = float(item.get("quantity") or 1)
            interval = recurring.get("interval")
            interval_count = float(recurring.get("interval_count") or 1)
            value = amount * quantity
            if interval == "year":
                value /= 12 * interval_count
            elif interval == "week":
                value *= 52 / (12 * interval_count)
            elif interval == "day":
                value *= 365 / (12 * interval_count)
            elif interval == "month":
                value /= interval_count
            total += value
        return total / 100

    def build_snapshot(
        self,
        account: dict[str, Any],
        customers: list[dict[str, Any]],
        subscriptions: list[dict[str, Any]],
        invoices: list[dict[str, Any]],
    ) -> dict[str, Any]:
        active_statuses = {"active", "trialing", "past_due"}
        active = [s for s in subscriptions if s.get("status") in active_statuses]
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        canceled_30d = [
            s for s in subscriptions
            if s.get("canceled_at")
            and datetime.fromtimestamp(s["canceled_at"], tz=timezone.utc)
            >= thirty_days_ago
        ]
        mrr = sum(self.monthly_value(s) for s in active)
        risky = [
            s for s in active
            if s.get("status") == "past_due" or s.get("cancel_at_period_end")
        ]
        revenue_at_risk = sum(self.monthly_value(s) for s in risky)
        opening_base = len(active) + len(canceled_30d)
        churn_rate = (
            round(len(canceled_30d) / opening_base * 100, 2)
            if opening_base else 0.0
        )
        paid_invoices = [
            invoice for invoice in invoices
            if invoice.get("status") == "paid"
            and invoice.get("created")
            and datetime.fromtimestamp(invoice["created"], tz=timezone.utc)
            >= thirty_days_ago
        ]
        revenue_30d = sum(float(i.get("amount_paid") or 0) for i in paid_invoices) / 100
        currency = str(account.get("default_currency") or "usd").upper()
        active_customer_ids = {s.get("customer") for s in active if s.get("customer")}
        return {
            "provider": "stripe",
            "account_id": account.get("id"),
            "business_name": (
                (account.get("business_profile") or {}).get("name")
                or account.get("email")
                or account.get("id")
            ),
            "currency": currency,
            "mrr": round(mrr, 2),
            "arr": round(mrr * 12, 2),
            "revenue": round(revenue_30d, 2),
            "active_customers": len(active_customer_ids),
            "total_customers": len(customers),
            "active_subscriptions": len(active),
            "canceled_subscriptions_30d": len(canceled_30d),
            "churn_rate": churn_rate,
            "retention_rate": round(100 - churn_rate, 2),
            "revenue_at_risk": round(revenue_at_risk, 2),
            "paid_invoices_30d": len(paid_invoices),
            "synced_at": utc_now(),
        }

    async def _fetch(self, secret_key: str) -> tuple[dict[str, Any], list, list, list]:
        async with httpx.AsyncClient(timeout=45) as client:
            account_response = await client.get(
                f"{STRIPE_API}/account", headers=self._headers(secret_key)
            )
            self._raise(account_response)
            account = account_response.json()
            customers = await self._list_all(
                client, "customers", secret_key, []
            )
            subscriptions = await self._list_all(
                client,
                "subscriptions",
                secret_key,
                [("status", "all"), ("expand[]", "data.items.data.price")],
            )
            invoices = await self._list_all(
                client, "invoices", secret_key, []
            )
        return account, customers, subscriptions, invoices

    async def connect(
        self, workspace_id: str, user_id: str, secret_key: str
    ) -> dict[str, Any]:
        if not secret_key.startswith(("sk_", "rk_")):
            raise ValueError("Use a Stripe secret key or restricted key.")
        account, customers, subscriptions, invoices = await self._fetch(secret_key)
        snapshot = self.build_snapshot(account, customers, subscriptions, invoices)
        connection = integration_store.save(
            workspace_id,
            self.provider,
            {
                "status": "connected",
                "account_id": account.get("id"),
                "business_name": snapshot["business_name"],
                "livemode": bool(account.get("charges_enabled")),
                "encrypted_secret_key": secret_service.encrypt(secret_key),
                "connected_by": user_id,
                "last_synced_at": snapshot["synced_at"],
                "summary": snapshot,
            },
        )
        self._save_snapshot(workspace_id, snapshot)
        log_agent_run(
            workspace_id,
            "integration_service",
            "stripe_connected",
            f"Connected Stripe account {account.get('id')}.",
            {"mode": "live_api", "provider": "stripe"},
            {},
            20,
        )
        return self.public_status(connection)

    async def sync(self, workspace_id: str) -> dict[str, Any]:
        connection = integration_store.get(workspace_id, self.provider)
        if not connection:
            raise ValueError("Stripe is not connected.")
        key = secret_service.decrypt(connection["encrypted_secret_key"])
        account, customers, subscriptions, invoices = await self._fetch(key)
        snapshot = self.build_snapshot(account, customers, subscriptions, invoices)
        self._save_snapshot(workspace_id, snapshot)
        updated = integration_store.save(
            workspace_id,
            self.provider,
            {
                **connection,
                "status": "connected",
                "last_synced_at": snapshot["synced_at"],
                "summary": snapshot,
            },
        )
        return self.public_status(updated)

    def _save_snapshot(self, workspace_id: str, snapshot: dict[str, Any]) -> None:
        integration_store.supersede_sources(workspace_id, "billing", "stripe")
        knowledge_graph.ingest(
            workspace_id,
            "billing",
            "Live billing — Stripe",
            snapshot,
            external_id="stripe",
            product_id=integration_store.product_id(workspace_id),
        )

    def status(self, workspace_id: str) -> dict[str, Any]:
        return self.public_status(
            integration_store.get(workspace_id, self.provider)
        )

    @staticmethod
    def public_status(connection: dict[str, Any] | None) -> dict[str, Any]:
        if not connection:
            return {"status": "not_connected", "connected": False}
        return {
            "status": connection.get("status", "connected"),
            "connected": True,
            "account_id": connection.get("account_id"),
            "business_name": connection.get("business_name"),
            "livemode": connection.get("livemode"),
            "last_synced_at": connection.get("last_synced_at"),
            "summary": connection.get("summary", {}),
        }

    def disconnect(self, workspace_id: str) -> bool:
        return integration_store.disconnect(workspace_id, self.provider)


stripe_integration = StripeIntegrationService()
