from __future__ import annotations

import json
from collections import Counter
from typing import Any


from app.core.config import get_settings
from app.core.repository import utc_now
from app.services.audit_service import log_agent_run
from app.services.integration_utils import integration_store
from app.services.knowledge_graph_service import knowledge_graph
from app.services.secret_service import secret_service


COMMON_ACTIVE_FIELDS = (
    "subscriptionStatus", "isActive", "active", "isApproved", "enabled"
)
COMMON_PAYMENT_FIELDS = (
    "lastPaymentAmount", "amountPaid", "paymentAmount", "totalPaid"
)


class FirestoreIntegrationService:
    provider = "firestore"

    def _client(
        self,
        service_account_info: dict[str, Any],
        database_id: str,
    ) -> Any:
        try:
            from google.cloud import firestore
            from google.oauth2 import service_account
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-firestore and google-auth are required for Firestore integration."
            ) from exc
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/datastore"],
        )
        return firestore.Client(
            project=service_account_info["project_id"],
            credentials=credentials,
            database=database_id or "(default)",
        )

    @staticmethod
    def _collection_names(client: Any) -> list[str]:
        return sorted(collection.id for collection in client.collections())

    @staticmethod
    def _is_active(record: dict[str, Any]) -> bool:
        for field in COMMON_ACTIVE_FIELDS:
            value = record.get(field)
            if isinstance(value, bool):
                return value
            if str(value).lower() in {"active", "paid", "true", "yes", "approved"}:
                return True
        return False

    @staticmethod
    def _has_paid(record: dict[str, Any]) -> bool:
        for field in COMMON_PAYMENT_FIELDS:
            try:
                if float(record.get(field) or 0) > 0:
                    return True
            except (TypeError, ValueError):
                continue
        return FirestoreIntegrationService._is_active(record)

    def _read_collection(
        self,
        client: Any,
        collection_name: str,
    ) -> tuple[list[dict[str, Any]], bool]:
        if not collection_name:
            return [], False
        limit = get_settings().firestore_sync_document_limit
        records: list[dict[str, Any]] = []
        for document in client.collection(collection_name).limit(limit + 1).stream():
            if len(records) >= limit:
                return records, True
            payload = document.to_dict() or {}
            payload["_id"] = document.id
            records.append(payload)
        return records, False

    def _build_snapshot(
        self,
        client: Any,
        mappings: dict[str, str],
        database_id: str,
    ) -> dict[str, Any]:
        collection_counts: dict[str, int] = {}
        capped_collections: list[str] = []
        field_frequency: Counter[str] = Counter()
        role_records: dict[str, list[dict[str, Any]]] = {}

        for role, collection_name in mappings.items():
            if not collection_name:
                continue
            records, capped = self._read_collection(client, collection_name)
            role_records[role] = records
            collection_counts[collection_name] = len(records)
            if capped:
                capped_collections.append(collection_name)
            for record in records[:250]:
                field_frequency.update(
                    key for key in record.keys() if not key.startswith("_")
                )

        customers = role_records.get("customers", [])
        accounts = role_records.get("accounts", [])
        subscriptions = role_records.get("subscriptions", [])
        events = role_records.get("events", [])
        documents = role_records.get("documents", [])

        active_customers = sum(1 for record in customers if self._is_active(record))
        paid_customers = sum(1 for record in customers if self._has_paid(record))
        active_accounts = sum(1 for record in accounts if self._is_active(record))

        return {
            "provider": "firestore",
            "project_id": client.project,
            "database_id": database_id or "(default)",
            "collection_mappings": mappings,
            "collection_counts": collection_counts,
            "capped_collections": capped_collections,
            "total_customers": len(customers),
            "active_customers": active_customers,
            "paid_customers": paid_customers,
            "total_accounts": len(accounts),
            "active_accounts": active_accounts,
            "subscription_records": len(subscriptions),
            "event_records": len(events),
            "document_records": len(documents),
            "common_fields": [name for name, _ in field_frequency.most_common(30)],
            "synced_at": utc_now(),
        }

    def connect(
        self,
        workspace_id: str,
        user_id: str,
        service_account_info: dict[str, Any],
        database_id: str,
        mappings: dict[str, str],
    ) -> dict[str, Any]:
        required = {"project_id", "client_email", "private_key", "token_uri"}
        missing = sorted(required - set(service_account_info))
        if missing:
            raise ValueError(
                "Service account JSON is missing: " + ", ".join(missing)
            )

        client = self._client(service_account_info, database_id)
        available_collections = self._collection_names(client)
        snapshot = self._build_snapshot(client, mappings, database_id)

        encrypted = secret_service.encrypt(
            json.dumps(service_account_info, separators=(",", ":"))
        )
        connection = integration_store.save(
            workspace_id,
            self.provider,
            {
                "status": "connected",
                "project_id": service_account_info["project_id"],
                "client_email": service_account_info["client_email"],
                "database_id": database_id,
                "collection_mappings": mappings,
                "available_collections": available_collections,
                "encrypted_service_account": encrypted,
                "connected_by": user_id,
                "last_synced_at": snapshot.get("synced_at"),
                "summary": snapshot,
            },
        )
        self._save_snapshot(workspace_id, snapshot)
        log_agent_run(
            workspace_id,
            "integration_service",
            "firestore_connected",
            f"Connected Firestore project {service_account_info['project_id']}.",
            {"mode": "live_api", "provider": "firestore"},
            {},
            25,
        )
        return self.public_status(connection)

    def sync(self, workspace_id: str) -> dict[str, Any]:
        connection = integration_store.get(workspace_id, self.provider)
        if not connection:
            raise ValueError("Firestore is not connected.")
        info = json.loads(
            secret_service.decrypt(connection["encrypted_service_account"])
        )
        client = self._client(info, connection.get("database_id", "(default)"))
        snapshot = self._build_snapshot(
            client,
            connection.get("collection_mappings", {}),
            connection.get("database_id", "(default)"),
        )
        self._save_snapshot(workspace_id, snapshot)
        updated = integration_store.save(
            workspace_id,
            self.provider,
            {
                **connection,
                "status": "connected",
                "available_collections": self._collection_names(client),
                "last_synced_at": snapshot.get("synced_at"),
                "summary": snapshot,
            },
        )
        return self.public_status(updated)

    def _save_snapshot(self, workspace_id: str, snapshot: dict[str, Any]) -> None:
        integration_store.supersede_sources(
            workspace_id, "database", "firestore"
        )
        knowledge_graph.ingest(
            workspace_id,
            "database",
            "Live product database — Firestore",
            snapshot,
            external_id="firestore",
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
            "project_id": connection.get("project_id"),
            "client_email": connection.get("client_email"),
            "database_id": connection.get("database_id"),
            "collection_mappings": connection.get("collection_mappings", {}),
            "available_collections": connection.get("available_collections", []),
            "last_synced_at": connection.get("last_synced_at"),
            "summary": connection.get("summary", {}),
        }

    def disconnect(self, workspace_id: str) -> bool:
        return integration_store.disconnect(workspace_id, self.provider)


firestore_integration = FirestoreIntegrationService()
