from __future__ import annotations

from collections import OrderedDict
from typing import Any

from app.core.repository import get_repository
from app.services.firestore_integration_service import firestore_integration
from app.services.github_service import github_service
from app.services.gmail_integration_service import gmail_integration
from app.services.posthog_integration_service import posthog_integration
from app.services.stripe_integration_service import stripe_integration
from app.services.whatsapp_integration_service import whatsapp_integration


class ContextBuilderService:
    """Builds a minimal, source-linked operating context for Kondai workflows."""

    def __init__(self) -> None:
        self.repo = get_repository()

    @staticmethod
    def _latest_active_source(
        sources: list[dict[str, Any]],
        source_type: str,
        external_id: str | None = None,
    ) -> dict[str, Any] | None:
        for source in sources:
            if source.get("status") != "connected":
                continue
            if source.get("source_type") != source_type:
                continue
            if external_id is not None and source.get("external_id") != external_id:
                continue
            return source
        return None

    @staticmethod
    def _display(value: Any, unit: str = "") -> str:
        if value is None:
            return "Unknown"
        if isinstance(value, float):
            value = round(value, 2)
        return f"{value} {unit}".strip()

    def _evidence(
        self,
        key: str,
        source_key: str,
        source_name: str,
        fact: str,
        value: Any,
        unit: str = "",
        confidence: float = 1.0,
        retrieved_at: str | None = None,
        source_object_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "key": key,
            "source_key": source_key,
            "source_name": source_name,
            "source_object_id": source_object_id,
            "fact": fact,
            "value": value,
            "unit": unit,
            "display_value": self._display(value, unit),
            "confidence": confidence,
            "retrieved_at": retrieved_at,
        }

    def build(self, workspace_id: str) -> dict[str, Any]:
        sources = self.repo.list("sources", workspace_id)
        products = self.repo.list("products", workspace_id)

        github = github_service.public_status(workspace_id)
        database = firestore_integration.status(workspace_id)
        billing = stripe_integration.status(workspace_id)
        analytics = posthog_integration.status(workspace_id)
        gmail = gmail_integration.status(workspace_id)
        whatsapp = whatsapp_integration.status(workspace_id)

        integrations = OrderedDict(
            github=github,
            firestore=database,
            stripe=billing,
            posthog=analytics,
            gmail=gmail,
            whatsapp=whatsapp,
        )
        connected = [
            key
            for key, status in integrations.items()
            if bool(status.get("connected"))
            or bool(status.get("repository_connected"))
        ]

        github_source = self._latest_active_source(sources, "github")
        database_source = self._latest_active_source(
            sources, "database", "firestore"
        ) or self._latest_active_source(sources, "database")
        billing_source = self._latest_active_source(
            sources, "billing", "stripe"
        ) or self._latest_active_source(sources, "billing")
        analytics_source = self._latest_active_source(
            sources, "analytics", "posthog"
        ) or self._latest_active_source(sources, "analytics")
        gmail_source = self._latest_active_source(
            sources, "support", "gmail"
        )
        whatsapp_source = self._latest_active_source(
            sources, "support", "whatsapp"
        )

        github_data = (github_source or {}).get("data", {})
        database_data = (database_source or {}).get("data", {})
        billing_data = (billing_source or {}).get("data", {})
        analytics_data = (analytics_source or {}).get("data", {})
        gmail_data = (gmail_source or {}).get("data", {})
        whatsapp_data = (whatsapp_source or {}).get("data", {})

        evidence: list[dict[str, Any]] = []

        def add(
            key: str,
            source_key: str,
            source_name: str,
            fact: str,
            value: Any,
            unit: str = "",
            confidence: float = 1.0,
            source: dict[str, Any] | None = None,
        ) -> None:
            if value in (None, ""):
                return
            evidence.append(
                self._evidence(
                    key,
                    source_key,
                    source_name,
                    fact,
                    value,
                    unit,
                    confidence,
                    (source or {}).get("updated_at")
                    or (source or {}).get("created_at"),
                    (source or {}).get("id"),
                )
            )

        if github_source:
            add(
                "github.repository",
                "github",
                github_source.get("name", "GitHub repository"),
                "Connected repository",
                github_data.get("repository")
                or github.get("selected_repository"),
                source=github_source,
            )
            add(
                "github.files",
                "github",
                github_source.get("name", "GitHub repository"),
                "Files indexed",
                github_data.get("file_count"),
                "files",
                source=github_source,
            )
            add(
                "github.languages",
                "github",
                github_source.get("name", "GitHub repository"),
                "Programming languages detected",
                len(github_data.get("languages", {}) or {}),
                "languages",
                source=github_source,
            )
            add(
                "github.commits",
                "github",
                github_source.get("name", "GitHub repository"),
                "Recent commits reviewed",
                github_data.get("recent_commits"),
                "commits",
                source=github_source,
            )
            add(
                "github.open_issues",
                "github",
                github_source.get("name", "GitHub repository"),
                "Open issues",
                github_data.get("open_bugs"),
                "issues",
                source=github_source,
            )
            add(
                "github.manifests",
                "github",
                github_source.get("name", "GitHub repository"),
                "Key manifests and documentation files read",
                len(github_data.get("manifests", {}) or {}),
                "files",
                source=github_source,
            )
            for index, feature in enumerate(
                (github_data.get("recent_features") or [])[:8]
            ):
                add(
                    f"github.feature.{index}",
                    "github",
                    github_source.get("name", "GitHub repository"),
                    "Recent product change",
                    feature,
                    source=github_source,
                )

        if database_source:
            database_metrics = {
                "database.customers": (
                    "Customer records reviewed",
                    database_data.get("total_customers"),
                    "customers",
                ),
                "database.active_customers": (
                    "Active customer records",
                    database_data.get("active_customers"),
                    "customers",
                ),
                "database.paid_customers": (
                    "Paid customer records",
                    database_data.get("paid_customers"),
                    "customers",
                ),
                "database.accounts": (
                    "Business or school accounts reviewed",
                    database_data.get("total_accounts"),
                    "accounts",
                ),
                "database.active_accounts": (
                    "Active business or school accounts",
                    database_data.get("active_accounts"),
                    "accounts",
                ),
                "database.subscriptions": (
                    "Subscription records reviewed",
                    database_data.get("subscription_records"),
                    "records",
                ),
                "database.events": (
                    "Product event records reviewed",
                    database_data.get("event_records"),
                    "events",
                ),
                "database.documents": (
                    "Generated document records reviewed",
                    database_data.get("document_records"),
                    "documents",
                ),
            }
            for key, (fact, value, unit) in database_metrics.items():
                add(
                    key,
                    "firestore",
                    database_source.get("name", "Product database"),
                    fact,
                    value,
                    unit,
                    source=database_source,
                )

        if billing_source:
            currency = str(billing_data.get("currency") or "")
            billing_metrics = {
                "billing.mrr": (
                    "Monthly recurring revenue",
                    billing_data.get("mrr"),
                    currency,
                ),
                "billing.arr": (
                    "Annual recurring revenue",
                    billing_data.get("arr"),
                    currency,
                ),
                "billing.active_subscriptions": (
                    "Active subscriptions",
                    billing_data.get("active_subscriptions"),
                    "subscriptions",
                ),
                "billing.active_customers": (
                    "Active paying customers",
                    billing_data.get("active_customers"),
                    "customers",
                ),
                "billing.churn_rate": (
                    "Estimated customer churn",
                    billing_data.get("churn_rate"),
                    "%",
                ),
                "billing.retention_rate": (
                    "Estimated customer retention",
                    billing_data.get("retention_rate"),
                    "%",
                ),
                "billing.revenue_at_risk": (
                    "Revenue at risk",
                    billing_data.get("revenue_at_risk"),
                    currency,
                ),
                "billing.revenue_30d": (
                    "Revenue collected in the previous 30 days",
                    billing_data.get("revenue"),
                    currency,
                ),
            }
            for key, (fact, value, unit) in billing_metrics.items():
                add(
                    key,
                    "stripe",
                    billing_source.get("name", "Billing"),
                    fact,
                    value,
                    unit,
                    source=billing_source,
                )

        if analytics_source:
            analytics_metrics = {
                "analytics.active_users": (
                    "Active users in the previous 30 days",
                    analytics_data.get("active_users"),
                    "users",
                ),
                "analytics.events": (
                    "Product events in the previous 30 days",
                    analytics_data.get("events_last_30_days"),
                    "events",
                ),
                "analytics.activated_users": (
                    "Users reaching the activation milestone",
                    analytics_data.get("activated_users"),
                    "users",
                ),
                "analytics.activation_rate": (
                    "Activation rate",
                    analytics_data.get("activation_rate"),
                    "%",
                ),
            }
            for key, (fact, value, unit) in analytics_metrics.items():
                add(
                    key,
                    "posthog",
                    analytics_source.get("name", "Product analytics"),
                    fact,
                    value,
                    unit,
                    source=analytics_source,
                )
            for index, (event, count) in enumerate(
                list((analytics_data.get("feature_usage") or {}).items())[:10]
            ):
                add(
                    f"analytics.feature.{index}",
                    "posthog",
                    analytics_source.get("name", "Product analytics"),
                    f"Usage of {event}",
                    count,
                    "events",
                    source=analytics_source,
                )

        for support_key, support_source, support_data in (
            ("gmail", gmail_source, gmail_data),
            ("whatsapp", whatsapp_source, whatsapp_data),
        ):
            if not support_source:
                continue
            add(
                f"support.{support_key}.open_tickets",
                support_key,
                support_source.get("name", "Customer conversations"),
                "Open customer issues",
                support_data.get("open_tickets"),
                "tickets",
                source=support_source,
            )
            messages = support_data.get("messages_received")
            if messages is None:
                messages = support_data.get("messages_imported")
            add(
                f"support.{support_key}.messages",
                support_key,
                support_source.get("name", "Customer conversations"),
                "Customer messages reviewed",
                messages,
                "messages",
                source=support_source,
            )
            for index, theme in enumerate((support_data.get("themes") or [])[:8]):
                if isinstance(theme, dict):
                    add(
                        f"support.{support_key}.theme.{index}",
                        support_key,
                        support_source.get("name", "Customer conversations"),
                        f"Customer theme: {theme.get('name', 'Unknown')}",
                        theme.get("count", 1),
                        "mentions",
                        source=support_source,
                    )

        data_gaps = []
        if not github.get("repository_connected"):
            data_gaps.append("GitHub codebase is not connected.")
        if not database.get("connected"):
            data_gaps.append("Product database is not connected.")
        if not billing.get("connected"):
            data_gaps.append(
                "Billing is not connected, so revenue and churn conclusions are limited."
            )
        if not analytics.get("connected"):
            data_gaps.append(
                "Product analytics is not connected, so activation and feature-use conclusions are limited."
            )
        if not gmail.get("connected") and not whatsapp.get("connected"):
            data_gaps.append(
                "No customer conversation source is connected, so customer themes are incomplete."
            )

        review_ready = bool(github.get("repository_connected")) and bool(
            database.get("connected")
        )
        missing_required = []
        if not github.get("repository_connected"):
            missing_required.append("GitHub repository")
        if not database.get("connected"):
            missing_required.append("Product Database")

        return {
            "review_ready": review_ready,
            "missing_required": missing_required,
            "connected_sources": connected,
            "integrations": integrations,
            "products": products[:3],
            "sources": {
                "github": github_data,
                "database": database_data,
                "billing": billing_data,
                "analytics": analytics_data,
                "gmail": gmail_data,
                "whatsapp": whatsapp_data,
            },
            "evidence": evidence,
            "data_gaps": data_gaps,
        }


context_builder = ContextBuilderService()
