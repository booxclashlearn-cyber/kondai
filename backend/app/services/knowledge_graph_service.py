from __future__ import annotations

from typing import Any

from app.core.repository import get_repository
from app.services.audit_service import log_agent_run


def _fact(
    label: str, value: Any, unit: str = "", confidence: float = 1.0
) -> dict[str, Any]:
    return {"label": label, "value": value, "unit": unit, "confidence": confidence}


def name_or_unknown(data: dict[str, Any]) -> str:
    return str(data.get("name") or "Unknown")


class KnowledgeGraphService:
    def __init__(self) -> None:
        self.repo = get_repository()

    def ingest(
        self,
        workspace_id: str,
        source_type: str,
        name: str,
        data: dict[str, Any],
        external_id: str = "",
        product_id: str | None = None,
    ) -> dict[str, Any]:
        source = self.repo.create(
            "sources",
            workspace_id,
            {
                "source_type": source_type,
                "name": name,
                "external_id": external_id,
                "product_id": product_id,
                "status": "connected",
                "data": data,
            },
        )
        facts = self._extract_facts(source_type, data)
        source_node = self.repo.create(
            "knowledge_nodes",
            workspace_id,
            {
                "node_type": "source",
                "label": name,
                "source_id": source["id"],
                "properties": {"source_type": source_type},
                "confidence": 1.0,
            },
        )
        for fact in facts:
            node = self.repo.create(
                "knowledge_nodes",
                workspace_id,
                {
                    "node_type": "fact",
                    "label": fact["label"],
                    "source_id": source["id"],
                    "product_id": product_id,
                    "properties": fact,
                    "confidence": fact.get("confidence", 1.0),
                },
            )
            self.repo.create(
                "knowledge_edges",
                workspace_id,
                {
                    "from_node_id": source_node["id"],
                    "to_node_id": node["id"],
                    "relation": "PROVIDES",
                    "source_id": source["id"],
                },
            )
        log_agent_run(
            workspace_id,
            "knowledge_graph",
            "source_ingestion",
            f"Ingested {name} and created {len(facts)} grounded facts.",
            {"mode": "deterministic", "source_type": source_type},
            {"source_id": source["id"]},
            12,
        )
        return {
            "source": source,
            "nodes_created": len(facts) + 1,
            "edges_created": len(facts),
        }

    @staticmethod
    def _extract_facts(source_type: str, data: dict[str, Any]) -> list[dict[str, Any]]:
        facts: list[dict[str, Any]] = []
        if source_type == "database":
            mapping = {
                "total_customers": ("Customer records", "customers"),
                "active_customers": ("Active customer records", "customers"),
                "paid_customers": ("Paid customer records", "customers"),
                "total_accounts": ("Account records", "accounts"),
                "active_accounts": ("Active account records", "accounts"),
                "subscription_records": ("Subscription records", "records"),
                "event_records": ("Product event records", "events"),
                "document_records": ("Generated document records", "documents"),
            }
            for key, (label, unit) in mapping.items():
                if key in data:
                    facts.append(_fact(label, data[key], unit))
            for collection, count in data.get("collection_counts", {}).items():
                facts.append(_fact(f"Collection size: {collection}", count, "records"))
        elif source_type == "billing":
            mapping = {
                "mrr": ("Monthly recurring revenue", data.get("currency", "")),
                "arr": ("Annual recurring revenue", data.get("currency", "")),
                "revenue": ("Recorded revenue — 30 days", data.get("currency", "")),
                "active_customers": ("Active paying customers", "customers"),
                "active_subscriptions": ("Active subscriptions", "subscriptions"),
                "churn_rate": ("Customer churn rate", "%"),
                "retention_rate": ("Customer retention rate", "%"),
                "revenue_at_risk": ("Revenue at risk", data.get("currency", "")),
            }
            for key, (label, unit) in mapping.items():
                if key in data:
                    facts.append(_fact(label, data[key], unit))
        elif source_type == "analytics":
            mapping = {
                "active_users": ("Active users — 30 days", "users"),
                "activation_rate": ("Activation rate", "%"),
                "activated_users": ("Activated users — 30 days", "users"),
                "events_last_30_days": ("Product events — 30 days", "events"),
            }
            for key, (label, unit) in mapping.items():
                if key in data:
                    facts.append(_fact(label, data[key], unit))
            for feature, usage in data.get("feature_usage", {}).items():
                facts.append(_fact(f"Feature usage: {feature}", usage, "events"))
        elif source_type == "github":
            facts.extend([
                _fact("Repository", data.get("repository", name_or_unknown(data))),
                _fact("Open bugs", data.get("open_bugs", 0), "issues"),
                _fact("Recent commits", data.get("recent_commits", 0), "commits"),
            ])
            for feature in data.get("recent_features", []):
                facts.append(_fact(f"Shipped feature: {feature}", True))
            for issue in data.get("critical_issues", []):
                facts.append(_fact(f"Critical issue: {issue}", True))
        elif source_type == "support":
            if "open_tickets" in data:
                facts.append(_fact("Open support tickets", data["open_tickets"], "tickets"))
            for theme in data.get("themes", []):
                if isinstance(theme, dict):
                    facts.append(_fact(
                        f"Support theme: {theme.get('name', 'Unknown')}",
                        theme.get("count", 1),
                        "mentions",
                    ))
            for request in data.get("feature_requests", []):
                facts.append(_fact(f"Feature request: {request}", True))
        elif source_type == "competitor":
            facts.append(_fact("Competitor", data.get("competitor", name_or_unknown(data))))
            if "pricing" in data:
                facts.append(_fact("Competitor pricing", data["pricing"]))
            for launch in data.get("launches", []):
                facts.append(_fact(f"Competitor launch: {launch}", True))
        elif source_type == "market":
            for trend in data.get("trends", []):
                facts.append(_fact(f"Market trend: {trend}", True, confidence=0.8))
            for pain in data.get("pain_points", []):
                facts.append(_fact(f"Market pain: {pain}", True, confidence=0.8))
        else:
            for key, value in data.items():
                if isinstance(value, (str, int, float, bool)):
                    facts.append(_fact(key.replace("_", " ").title(), value))
        return [item for item in facts if item["value"] not in (None, "")]

    def graph(self, workspace_id: str) -> dict[str, Any]:
        return {
            "sources": self.repo.list("sources", workspace_id),
            "nodes": self.repo.list("knowledge_nodes", workspace_id),
            "edges": self.repo.list("knowledge_edges", workspace_id),
        }

    def verified_facts(self, workspace_id: str) -> list[dict[str, Any]]:
        active_source_ids = {
            source["id"]
            for source in self.repo.list("sources", workspace_id)
            if source.get("status") == "connected"
        }
        return [
            node
            for node in self.repo.list("knowledge_nodes", workspace_id)
            if node.get("node_type") == "fact"
            and node.get("source_id") in active_source_ids
        ]


knowledge_graph = KnowledgeGraphService()
