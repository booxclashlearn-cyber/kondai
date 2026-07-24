from __future__ import annotations

from typing import Any

from app.core.repository import get_repository, utc_now


class IntegrationStore:
    def __init__(self) -> None:
        self.repo = get_repository()

    def get(self, workspace_id: str, provider: str) -> dict[str, Any] | None:
        return self.repo.get("integration_connections", provider, workspace_id)

    def save(
        self,
        workspace_id: str,
        provider: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        current = self.get(workspace_id, provider)
        data = {
            **payload,
            "id": provider,
            "provider": provider,
            "updated_at_external": utc_now(),
        }
        if current:
            return self.repo.update(
                "integration_connections", provider, workspace_id, data
            ) or current
        return self.repo.create("integration_connections", workspace_id, data)

    def disconnect(self, workspace_id: str, provider: str) -> bool:
        return self.repo.delete(
            "integration_connections", provider, workspace_id
        )

    def product_id(self, workspace_id: str) -> str | None:
        github = self.get(workspace_id, "github")
        if github and github.get("product_id"):
            return str(github["product_id"])
        products = self.repo.list("products", workspace_id)
        return products[0]["id"] if products else None

    def supersede_sources(
        self,
        workspace_id: str,
        source_type: str,
        external_id: str,
    ) -> None:
        for source in self.repo.list("sources", workspace_id):
            if (
                source.get("source_type") == source_type
                and source.get("external_id") == external_id
                and source.get("status") == "connected"
            ):
                self.repo.update(
                    "sources", source["id"], workspace_id,
                    {"status": "superseded"},
                )


integration_store = IntegrationStore()
