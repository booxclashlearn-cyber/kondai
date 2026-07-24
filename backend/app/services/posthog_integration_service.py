from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.repository import utc_now
from app.services.audit_service import log_agent_run
from app.services.integration_utils import integration_store
from app.services.knowledge_graph_service import knowledge_graph
from app.services.secret_service import secret_service


class PostHogIntegrationService:
    provider = "posthog"

    @staticmethod
    def _normalise_host(host: str) -> str:
        host = host.strip().rstrip("/")
        parsed = urlparse(host)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("Enter a valid PostHog host URL.")
        return host

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("'", "''")

    async def _query(
        self,
        host: str,
        project_id: str,
        api_key: str,
        sql: str,
        name: str,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{host}/api/projects/{project_id}/query/",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": {"kind": "HogQLQuery", "query": sql},
                    "name": name,
                },
            )
        if not response.is_success:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise ValueError(f"PostHog query failed: {detail}")
        return response.json()

    @staticmethod
    def _rows(payload: dict[str, Any]) -> list[list[Any]]:
        results = payload.get("results") or []
        return results if isinstance(results, list) else []

    async def _build_snapshot(
        self,
        host: str,
        project_id: str,
        api_key: str,
        activation_event: str,
    ) -> dict[str, Any]:
        summary = await self._query(
            host,
            project_id,
            api_key,
            "SELECT count() AS events_30d, uniq(distinct_id) AS active_users "
            "FROM events WHERE timestamp >= now() - INTERVAL 30 DAY",
            "Kondai analytics summary",
        )
        top_events = await self._query(
            host,
            project_id,
            api_key,
            "SELECT event, count() AS event_count, uniq(distinct_id) AS users "
            "FROM events WHERE timestamp >= now() - INTERVAL 30 DAY "
            "GROUP BY event ORDER BY event_count DESC LIMIT 20",
            "Kondai top product events",
        )
        summary_rows = self._rows(summary)
        events_30d = int(summary_rows[0][0] or 0) if summary_rows else 0
        active_users = int(summary_rows[0][1] or 0) if summary_rows else 0
        feature_usage: dict[str, int] = {}
        unique_users_by_event: dict[str, int] = {}
        for row in self._rows(top_events):
            if len(row) >= 3:
                feature_usage[str(row[0])] = int(row[1] or 0)
                unique_users_by_event[str(row[0])] = int(row[2] or 0)

        activated_users = 0
        activation_rate = 0.0
        if activation_event:
            escaped = self._escape(activation_event)
            activation = await self._query(
                host,
                project_id,
                api_key,
                "SELECT uniq(distinct_id) FROM events "
                "WHERE timestamp >= now() - INTERVAL 30 DAY "
                f"AND event = '{escaped}'",
                "Kondai activation event",
            )
            rows = self._rows(activation)
            activated_users = int(rows[0][0] or 0) if rows else 0
            activation_rate = (
                round(activated_users / active_users * 100, 2)
                if active_users else 0.0
            )

        return {
            "provider": "posthog",
            "host": host,
            "project_id": project_id,
            "active_users": active_users,
            "events_last_30_days": events_30d,
            "activation_event": activation_event,
            "activated_users": activated_users,
            "activation_rate": activation_rate,
            "feature_usage": feature_usage,
            "unique_users_by_event": unique_users_by_event,
            "synced_at": utc_now(),
        }

    async def connect(
        self,
        workspace_id: str,
        user_id: str,
        host: str,
        project_id: str,
        api_key: str,
        activation_event: str,
    ) -> dict[str, Any]:
        host = self._normalise_host(host)
        snapshot = await self._build_snapshot(
            host, project_id, api_key, activation_event.strip()
        )
        connection = integration_store.save(
            workspace_id,
            self.provider,
            {
                "status": "connected",
                "host": host,
                "project_id": project_id,
                "activation_event": activation_event.strip(),
                "encrypted_personal_api_key": secret_service.encrypt(api_key),
                "connected_by": user_id,
                "last_synced_at": snapshot["synced_at"],
                "summary": snapshot,
            },
        )
        self._save_snapshot(workspace_id, snapshot)
        log_agent_run(
            workspace_id,
            "integration_service",
            "posthog_connected",
            f"Connected PostHog project {project_id}.",
            {"mode": "live_api", "provider": "posthog"},
            {},
            20,
        )
        return self.public_status(connection)

    async def sync(self, workspace_id: str) -> dict[str, Any]:
        connection = integration_store.get(workspace_id, self.provider)
        if not connection:
            raise ValueError("PostHog is not connected.")
        key = secret_service.decrypt(connection["encrypted_personal_api_key"])
        snapshot = await self._build_snapshot(
            connection["host"],
            str(connection["project_id"]),
            key,
            connection.get("activation_event", ""),
        )
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
        integration_store.supersede_sources(workspace_id, "analytics", "posthog")
        knowledge_graph.ingest(
            workspace_id,
            "analytics",
            "Live product analytics — PostHog",
            snapshot,
            external_id="posthog",
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
            "host": connection.get("host"),
            "project_id": connection.get("project_id"),
            "activation_event": connection.get("activation_event"),
            "last_synced_at": connection.get("last_synced_at"),
            "summary": connection.get("summary", {}),
        }

    def disconnect(self, workspace_id: str) -> bool:
        return integration_store.disconnect(workspace_id, self.provider)


posthog_integration = PostHogIntegrationService()
