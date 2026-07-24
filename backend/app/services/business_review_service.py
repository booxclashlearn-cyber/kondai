from __future__ import annotations

from typing import Any

from app.core.repository import get_repository
from app.models.schemas import BusinessReviewOutput
from app.services.audit_service import log_agent_run
from app.services.context_builder_service import context_builder
from app.services.gemini_service import gemini


class BusinessReviewService:
    """Creates a founder-facing, evidence-linked review from live integrations."""

    def __init__(self) -> None:
        self.repo = get_repository()

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _finding(
        title: str,
        category: str,
        severity: str,
        summary: str,
        why_it_matters: str,
        evidence_ids: list[str],
    ) -> dict[str, Any]:
        return {
            "title": title,
            "category": category,
            "severity": severity,
            "summary": summary,
            "why_it_matters": why_it_matters,
            "evidence_ids": evidence_ids,
        }

    def _fallback(self, context: dict[str, Any]) -> dict[str, Any]:
        github = context["sources"]["github"]
        database = context["sources"]["database"]
        billing = context["sources"]["billing"]
        analytics = context["sources"]["analytics"]
        support = {
            **context["sources"].get("gmail", {}),
            **context["sources"].get("whatsapp", {}),
        }

        findings: list[dict[str, Any]] = []
        file_count = self._number(github.get("file_count"))
        commits = self._number(github.get("recent_commits"))
        open_issues = self._number(github.get("open_bugs"))
        languages = len(github.get("languages", {}) or {})
        total_customers = self._number(database.get("total_customers"))
        active_customers = self._number(database.get("active_customers"))
        paid_customers = self._number(database.get("paid_customers"))
        total_accounts = self._number(database.get("total_accounts"))
        active_accounts = self._number(database.get("active_accounts"))
        activation_rate = self._number(analytics.get("activation_rate"), -1)
        churn = self._number(billing.get("churn_rate"), -1)
        revenue_at_risk = self._number(billing.get("revenue_at_risk"))
        open_tickets = self._number(support.get("open_tickets"))

        if file_count or commits or languages:
            findings.append(
                self._finding(
                    "The product has a substantial, actively changing codebase",
                    "product",
                    "medium",
                    (
                        f"Kondai reviewed {int(file_count)} files across "
                        f"{languages} detected languages and {int(commits)} recent commits."
                    ),
                    "The product already contains meaningful capability; growth and support work should be grounded in what is actually shipped.",
                    [
                        key
                        for key in (
                            "github.files",
                            "github.languages",
                            "github.commits",
                        )
                        if any(item["key"] == key for item in context["evidence"])
                    ],
                )
            )

        if total_customers or total_accounts:
            customer_summary = f"Kondai reviewed {int(total_customers)} customer records"
            if total_accounts:
                customer_summary += f" and {int(total_accounts)} business or school accounts"
            customer_summary += "."
            findings.append(
                self._finding(
                    "There is an existing customer base to activate before relying only on new acquisition",
                    "customer",
                    "high" if total_customers >= 20 else "medium",
                    customer_summary,
                    "Existing users provide the fastest source of activation, renewal, feedback and referrals.",
                    [
                        key
                        for key in (
                            "database.customers",
                            "database.active_customers",
                            "database.paid_customers",
                            "database.accounts",
                            "database.active_accounts",
                        )
                        if any(item["key"] == key for item in context["evidence"])
                    ],
                )
            )

        if activation_rate >= 0:
            severity = "critical" if activation_rate < 15 else "high" if activation_rate < 35 else "medium"
            findings.append(
                self._finding(
                    "Activation is the clearest measurable product-growth signal",
                    "growth",
                    severity,
                    f"The connected analytics source reports an activation rate of {activation_rate:.1f}%.",
                    "Customers who do not reach first value are less likely to retain, recommend or upgrade.",
                    ["analytics.activation_rate"],
                )
            )

        if churn >= 0:
            severity = "critical" if churn >= 30 else "high" if churn >= 15 else "medium"
            findings.append(
                self._finding(
                    "Recurring revenue is being constrained by customer loss",
                    "revenue",
                    severity,
                    f"The connected billing source reports estimated churn of {churn:.1f}%.",
                    "Retention improvements compound revenue and reduce the amount of acquisition needed to grow.",
                    [
                        key
                        for key in ("billing.churn_rate", "billing.revenue_at_risk")
                        if any(item["key"] == key for item in context["evidence"])
                    ],
                )
            )

        if open_issues > 0:
            findings.append(
                self._finding(
                    "Open product issues need to be compared with customer impact",
                    "product",
                    "high" if open_issues >= 10 else "medium",
                    f"The repository currently contains {int(open_issues)} open issues.",
                    "Engineering priority should reflect customer and revenue impact rather than issue count alone.",
                    ["github.open_issues"],
                )
            )

        if open_tickets > 0:
            findings.append(
                self._finding(
                    "Customer conversations contain unresolved operating signals",
                    "customer",
                    "high" if open_tickets >= 10 else "medium",
                    f"There are {int(open_tickets)} open customer issues in connected support channels.",
                    "Repeated questions and complaints can reveal onboarding failures, bugs and unmet needs before dashboard metrics do.",
                    [
                        item["key"]
                        for item in context["evidence"]
                        if item["key"].startswith("support.")
                    ][:8],
                )
            )

        if context["data_gaps"]:
            findings.append(
                self._finding(
                    "The current review is useful but not yet complete",
                    "evidence",
                    "medium",
                    " ".join(context["data_gaps"]),
                    "Kondai should distinguish verified conclusions from areas where a missing source lowers confidence.",
                    [],
                )
            )

        if churn >= 15 or revenue_at_risk > 0:
            recommendation = {
                "title": "Prepare a focused renewal and win-back campaign",
                "objective": "Retention",
                "action": "Identify recently inactive or at-risk paying customers, prepare a three-touch re-engagement sequence and measure replies, logins and renewed activity.",
                "why_now": "These customers already know the product and are usually less expensive to recover than replacing them with new acquisition.",
                "expected_impact": "Protect recurring revenue, recover active usage and learn the main reasons customers disengage.",
                "confidence": 0.88 if billing else 0.72,
                "risk_level": "medium",
                "owner_workflow": "growth",
                "suggested_channel": "email",
                "audience": "Recently inactive or at-risk paying customers",
                "success_metric": "Reply rate, return-to-product rate and retained recurring revenue after 7 days",
                "time_horizon": "7 days",
                "alternatives": [
                    "Run a broader acquisition campaign, but this ranks lower because existing customers are warmer.",
                    "Change pricing immediately, but evidence about price sensitivity is not yet strong enough.",
                ],
                "evidence_ids": [
                    key
                    for key in (
                        "billing.churn_rate",
                        "billing.revenue_at_risk",
                        "database.paid_customers",
                        "database.customers",
                    )
                    if any(item["key"] == key for item in context["evidence"])
                ],
            }
        elif activation_rate >= 0 and activation_rate < 40:
            recommendation = {
                "title": "Prepare a first-value activation rescue",
                "objective": "Activation",
                "action": "Segment users who registered but did not reach the activation milestone, prepare a guided return message and measure first successful product activity.",
                "why_now": "The largest avoidable loss happens before users experience the product's core value.",
                "expected_impact": "Increase activated users and reveal the onboarding steps causing abandonment.",
                "confidence": 0.9,
                "risk_level": "low",
                "owner_workflow": "growth",
                "suggested_channel": "email",
                "audience": "Registered users who have not reached first value",
                "success_metric": "Activation milestone completion within 7 days",
                "time_horizon": "7 days",
                "alternatives": [
                    "Redesign onboarding immediately, but a focused rescue campaign can first reveal where users are stuck.",
                    "Acquire more users, but that would send more people into the same weak activation journey.",
                ],
                "evidence_ids": [
                    key
                    for key in (
                        "analytics.activation_rate",
                        "analytics.active_users",
                        "database.customers",
                        "database.active_customers",
                    )
                    if any(item["key"] == key for item in context["evidence"])
                ],
            }
        elif total_customers > active_customers and total_customers > 0:
            recommendation = {
                "title": "Prepare an activation and customer-discovery campaign",
                "objective": "Activation and learning",
                "action": "Identify customer records that appear inactive, prepare a helpful return message, ask one structured question about the main blocker and track renewed product activity.",
                "why_now": "The product already has an audience, but the connected database indicates that not every recorded customer is active.",
                "expected_impact": "Recover user activity and collect evidence about onboarding, product fit and unmet needs.",
                "confidence": 0.76,
                "risk_level": "low",
                "owner_workflow": "growth",
                "suggested_channel": "email",
                "audience": "Inactive existing customers",
                "success_metric": "Reply rate and return-to-product activity within 7 days",
                "time_horizon": "7 days",
                "alternatives": [
                    "Start a cold acquisition campaign, but existing users provide faster learning.",
                    "Build more features first, but the strongest missing evidence is why current users are inactive.",
                ],
                "evidence_ids": [
                    key
                    for key in (
                        "database.customers",
                        "database.active_customers",
                        "github.files",
                        "github.commits",
                    )
                    if any(item["key"] == key for item in context["evidence"])
                ],
            }
        elif open_issues > 0:
            recommendation = {
                "title": "Prepare a customer-impact issue review",
                "objective": "Reliability",
                "action": "Rank open repository issues by affected customer journey, support mentions and revenue impact, then prepare the highest-impact engineering task for approval.",
                "why_now": "The codebase contains unresolved issues, but issue priority should be grounded in business impact.",
                "expected_impact": "Reduce product friction and focus engineering effort on the most valuable reliability improvement.",
                "confidence": 0.73,
                "risk_level": "low",
                "owner_workflow": "engineering",
                "suggested_channel": "internal_task",
                "audience": "Product and engineering",
                "success_metric": "Highest-impact issue assigned with evidence and acceptance criteria",
                "time_horizon": "3 days",
                "alternatives": [
                    "Work through issues by age, but age does not prove customer impact.",
                    "Ship a new feature, but unresolved friction may reduce adoption of new capability.",
                ],
                "evidence_ids": ["github.open_issues"],
            }
        else:
            recommendation = {
                "title": "Prepare a structured customer activation baseline",
                "objective": "Measurement",
                "action": "Define the first-value milestone, map it to database records and connect product analytics before launching a larger growth action.",
                "why_now": "GitHub and the product database provide product and customer context, but the system needs a measurable activation event to evaluate growth actions.",
                "expected_impact": "Create a trustworthy baseline for activation, retention and future experiments.",
                "confidence": 0.82,
                "risk_level": "low",
                "owner_workflow": "engineering",
                "suggested_channel": "internal_task",
                "audience": "Founder and product team",
                "success_metric": "Activation event defined and measurable",
                "time_horizon": "3 days",
                "alternatives": [
                    "Launch a campaign immediately, but the result would be difficult to measure.",
                    "Wait for every integration, but the activation baseline can be prepared now.",
                ],
                "evidence_ids": [
                    key
                    for key in ("github.repository", "database.customers")
                    if any(item["key"] == key for item in context["evidence"])
                ],
            }

        scope = []
        if github:
            scope.append("Codebase and recent product changes")
        if database:
            scope.append("Customer, account and product records")
        if billing:
            scope.append("Revenue, subscriptions and retention")
        if analytics:
            scope.append("Activation and product usage")
        if support:
            scope.append("Customer questions and support themes")

        product_name = (
            context.get("products", [{}])[0].get("name")
            if context.get("products")
            else "your product"
        )
        return {
            "opening_message": "I have gone through the connected codebase and business records. Here is what I found.",
            "executive_summary": (
                f"{product_name} has a real product foundation and an existing customer base. "
                "The strongest next step should use those assets to improve measurable customer activity before expanding effort."
            ),
            "review_scope": scope,
            "data_gaps": context["data_gaps"],
            "findings": findings[:7],
            "recommendation": recommendation,
        }

    async def run(
        self,
        workspace_id: str,
        operation_run_id: str,
    ) -> dict[str, Any]:
        context = context_builder.build(workspace_id)
        if not context["review_ready"]:
            missing = ", ".join(context["missing_required"])
            raise ValueError(
                f"Connect the required sources before the review: {missing}."
            )

        evidence_records = []
        for item in context["evidence"]:
            evidence_records.append(
                self.repo.create(
                    "evidence_bundles",
                    workspace_id,
                    {
                        "id": f"{operation_run_id}-{item['key'].replace('.', '-')}",
                        "operation_run_id": operation_run_id,
                        **item,
                    },
                )
            )

        fallback = self._fallback(context)
        compact_context = {
            "connected_sources": context["connected_sources"],
            "products": context["products"],
            "sources": context["sources"],
            "evidence": [
                {
                    "key": item["key"],
                    "source": item["source_name"],
                    "fact": item["fact"],
                    "value": item["display_value"],
                    "confidence": item["confidence"],
                }
                for item in context["evidence"]
            ],
            "data_gaps": context["data_gaps"],
        }
        output, metadata = await gemini.generate_structured(
            BusinessReviewOutput,
            (
                "You are Kondai, an evidence-grounded operating partner for a founder. "
                "Review the connected product and business sources, state what was reviewed, "
                "identify ranked findings, and recommend exactly one next action. Every finding "
                "and recommendation must reference only evidence keys supplied in the prompt. "
                "Do not invent metrics, customers, product capabilities or completed actions. "
                "Do not expose private chain-of-thought. Use concise executive reasons."
            ),
            (
                "Create the initial business review from this verified context:\n"
                f"{compact_context}\n"
                "Use a founder-facing voice beginning with 'I have gone through...'. "
                "The recommendation should be specific enough that Kondai can prepare work after approval."
            ),
            fallback,
            0.15,
        )

        valid_evidence_keys = {item["key"] for item in context["evidence"]}
        payload = output.model_dump()
        for finding in payload["findings"]:
            finding["evidence_ids"] = [
                item for item in finding.get("evidence_ids", [])
                if item in valid_evidence_keys
            ]
        payload["recommendation"]["evidence_ids"] = [
            item for item in payload["recommendation"].get("evidence_ids", [])
            if item in valid_evidence_keys
        ]

        review = self.repo.create(
            "business_reviews",
            workspace_id,
            {
                "operation_run_id": operation_run_id,
                **payload,
                "status": "awaiting_founder",
                "connected_sources": context["connected_sources"],
                "evidence_count": len(evidence_records),
                "model_metadata": metadata,
            },
        )

        finding_records = []
        for finding in payload["findings"]:
            finding_records.append(
                self.repo.create(
                    "review_findings",
                    workspace_id,
                    {
                        **finding,
                        "business_review_id": review["id"],
                        "operation_run_id": operation_run_id,
                        "status": "active",
                    },
                )
            )

        rec = payload["recommendation"]
        recommendation = self.repo.create(
            "recommendations",
            workspace_id,
            {
                "business_review_id": review["id"],
                "operation_run_id": operation_run_id,
                "title": rec["title"],
                "priority": "high",
                "action": rec["action"],
                "reason": rec["why_now"],
                "expected_impact": rec["expected_impact"],
                "objective": rec["objective"],
                "confidence": rec["confidence"],
                "risk_level": rec["risk_level"],
                "owner_workflow": rec["owner_workflow"],
                "owner_agent": (
                    "growth_agent"
                    if rec["owner_workflow"] == "growth"
                    else "support_agent"
                    if rec["owner_workflow"] == "support"
                    else "founder"
                ),
                "suggested_channel": rec["suggested_channel"],
                "audience": rec["audience"],
                "success_metric": rec["success_metric"],
                "time_horizon": rec["time_horizon"],
                "alternatives": rec["alternatives"],
                "evidence_ids": rec["evidence_ids"],
                "status": "awaiting_founder",
                "founder_note": "",
            },
        )
        self.repo.update(
            "business_reviews",
            review["id"],
            workspace_id,
            {
                "recommendation_id": recommendation["id"],
                "finding_ids": [item["id"] for item in finding_records],
            },
        )

        log_agent_run(
            workspace_id,
            "operating_review",
            "initial_business_review",
            (
                f"Reviewed {len(context['connected_sources'])} connected sources, "
                f"created {len(finding_records)} findings and proposed one next action."
            ),
            metadata,
            {
                "operation_run_id": operation_run_id,
                "business_review_id": review["id"],
                "recommendation_id": recommendation["id"],
            },
            90,
        )
        return {
            "review": self.repo.get(
                "business_reviews", review["id"], workspace_id
            ),
            "findings": finding_records,
            "recommendation": recommendation,
            "evidence": evidence_records,
        }


business_review_service = BusinessReviewService()
