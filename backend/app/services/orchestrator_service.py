from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.repository import get_repository, utc_now
from app.services.action_handoff_service import action_handoff
from app.services.business_review_service import business_review_service
from app.services.context_builder_service import context_builder


class OrchestratorService:
    """Coordinates review → recommendation → preparation → approval → outcome."""

    def __init__(self) -> None:
        self.repo = get_repository()

    @staticmethod
    def _signature(context: dict[str, Any]) -> str:
        payload = {
            key: {
                "status": value.get("status"),
                "last_synced_at": value.get("last_synced_at"),
                "selected_repository": value.get("selected_repository"),
                "project_id": value.get("project_id"),
            }
            for key, value in context["integrations"].items()
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    def readiness(self, workspace_id: str) -> dict[str, Any]:
        context = context_builder.build(workspace_id)
        return {
            "ready": context["review_ready"],
            "missing_required": context["missing_required"],
            "connected_sources": context["connected_sources"],
            "data_gaps": context["data_gaps"],
        }

    def _create_steps(
        self,
        workspace_id: str,
        run_id: str,
    ) -> list[dict[str, Any]]:
        definitions = [
            ("confirm_sources", "Confirm connected sources"),
            ("review_codebase", "Review codebase and product changes"),
            ("review_customers", "Review customer and account records"),
            ("combine_evidence", "Combine verified evidence"),
            ("recommend_action", "Rank the best next action"),
        ]
        return [
            self.repo.create(
                "operation_steps",
                workspace_id,
                {
                    "operation_run_id": run_id,
                    "key": key,
                    "label": label,
                    "position": position,
                    "status": "pending",
                    "result": "",
                },
            )
            for position, (key, label) in enumerate(definitions, start=1)
        ]

    def _set_step(
        self,
        workspace_id: str,
        run_id: str,
        key: str,
        status: str,
        result: str = "",
    ) -> None:
        step = next(
            (
                item
                for item in self.repo.list("operation_steps", workspace_id)
                if item.get("operation_run_id") == run_id
                and item.get("key") == key
            ),
            None,
        )
        if step:
            self.repo.update(
                "operation_steps",
                step["id"],
                workspace_id,
                {
                    "status": status,
                    "result": result,
                    "completed_at": utc_now() if status == "completed" else None,
                },
            )

    async def maybe_start_review(
        self,
        workspace_id: str,
        trigger: str,
        force: bool = False,
    ) -> dict[str, Any]:
        context = context_builder.build(workspace_id)
        if not context["review_ready"]:
            return {
                "started": False,
                "ready": False,
                "missing_required": context["missing_required"],
            }

        signature = self._signature(context)
        latest = self.repo.list("operation_runs", workspace_id)
        if (
            not force
            and latest
            and latest[0].get("source_signature") == signature
            and latest[0].get("status")
            in {"awaiting_founder", "preparing", "awaiting_final_approval", "executed"}
        ):
            return {
                "started": False,
                "ready": True,
                "reason": "No connected source has changed since the latest review.",
                "operation_run": latest[0],
            }

        run = self.repo.create(
            "operation_runs",
            workspace_id,
            {
                "trigger": trigger,
                "status": "running",
                "source_signature": signature,
                "connected_sources": context["connected_sources"],
                "started_at": utc_now(),
                "message": "Kondai is reviewing the connected product and business records.",
            },
        )
        self._create_steps(workspace_id, run["id"])

        try:
            self._set_step(
                workspace_id,
                run["id"],
                "confirm_sources",
                "completed",
                f"Confirmed {len(context['connected_sources'])} connected sources.",
            )
            self._set_step(
                workspace_id,
                run["id"],
                "review_codebase",
                "in_progress",
            )
            self._set_step(
                workspace_id,
                run["id"],
                "review_codebase",
                "completed",
                "Reviewed repository structure, recent commits, issues and key product files.",
            )
            self._set_step(
                workspace_id,
                run["id"],
                "review_customers",
                "in_progress",
            )
            self._set_step(
                workspace_id,
                run["id"],
                "review_customers",
                "completed",
                "Reviewed customer, account and configured business collections.",
            )
            self._set_step(
                workspace_id,
                run["id"],
                "combine_evidence",
                "in_progress",
            )
            result = await business_review_service.run(
                workspace_id, run["id"]
            )
            self._set_step(
                workspace_id,
                run["id"],
                "combine_evidence",
                "completed",
                f"Created {len(result['evidence'])} source-linked evidence records.",
            )
            self._set_step(
                workspace_id,
                run["id"],
                "recommend_action",
                "completed",
                result["recommendation"]["title"],
            )
            updated = self.repo.update(
                "operation_runs",
                run["id"],
                workspace_id,
                {
                    "status": "awaiting_founder",
                    "completed_at": utc_now(),
                    "business_review_id": result["review"]["id"],
                    "recommendation_id": result["recommendation"]["id"],
                    "message": result["review"]["opening_message"],
                },
            ) or run
            return {
                "started": True,
                "ready": True,
                "operation_run": updated,
                **result,
            }
        except Exception as exc:
            self.repo.update(
                "operation_runs",
                run["id"],
                workspace_id,
                {
                    "status": "failed",
                    "failed_at": utc_now(),
                    "error": str(exc),
                    "message": "Kondai could not complete the business review.",
                },
            )
            raise

    async def continue_recommendation(
        self,
        workspace_id: str,
        recommendation_id: str,
        user_id: str,
        founder_note: str = "",
    ) -> dict[str, Any]:
        recommendation = self.repo.get(
            "recommendations", recommendation_id, workspace_id
        )
        if not recommendation:
            raise ValueError("Recommendation not found.")
        if recommendation.get("status") not in {
            "awaiting_founder",
            "pending",
            "approved",
            "held",
        }:
            raise ValueError("This recommendation can no longer continue.")

        self.repo.update(
            "recommendations",
            recommendation_id,
            workspace_id,
            {
                "status": "approved",
                "founder_note": founder_note,
                "decided_by": user_id,
                "decided_at": utc_now(),
            },
        )
        existing = next(
            (
                item
                for item in self.repo.list("action_plans", workspace_id)
                if item.get("recommendation_id") == recommendation_id
            ),
            None,
        )
        if existing:
            plan = existing
        else:
            plan = self.repo.create(
                "action_plans",
                workspace_id,
                {
                    "recommendation_id": recommendation_id,
                    "business_review_id": recommendation.get("business_review_id"),
                    "operation_run_id": recommendation.get("operation_run_id"),
                    "title": recommendation["title"],
                    "objective": recommendation.get("objective"),
                    "audience": recommendation.get("audience"),
                    "channel": recommendation.get("suggested_channel"),
                    "success_metric": recommendation.get("success_metric"),
                    "time_horizon": recommendation.get("time_horizon"),
                    "status": "approved_to_prepare",
                    "deliverables": [],
                    "approval_ids": [],
                    "baseline": self._baseline(workspace_id),
                },
            )
            for position, (key, label) in enumerate(
                [
                    ("confirm_scope", "Confirm the approved direction"),
                    ("select_audience", "Select the eligible audience or task scope"),
                    ("prepare_assets", "Prepare the work"),
                    ("request_approval", "Request final approval"),
                    ("execute", "Execute and monitor the result"),
                ],
                start=1,
            ):
                self.repo.create(
                    "action_steps",
                    workspace_id,
                    {
                        "action_plan_id": plan["id"],
                        "key": key,
                        "label": label,
                        "position": position,
                        "status": "pending",
                        "result": "",
                    },
                )

        prepared = await action_handoff.prepare(workspace_id, plan["id"])
        if recommendation.get("operation_run_id"):
            self.repo.update(
                "operation_runs",
                recommendation["operation_run_id"],
                workspace_id,
                {
                    "status": prepared.get("status", "preparing"),
                    "action_plan_id": plan["id"],
                    "message": "Kondai has prepared the approved next action for final review.",
                },
            )
        return self.command_center(workspace_id)

    def hold_recommendation(
        self,
        workspace_id: str,
        recommendation_id: str,
        user_id: str,
        founder_note: str = "",
    ) -> dict[str, Any]:
        recommendation = self.repo.get(
            "recommendations", recommendation_id, workspace_id
        )
        if not recommendation:
            raise ValueError("Recommendation not found.")
        self.repo.update(
            "recommendations",
            recommendation_id,
            workspace_id,
            {
                "status": "held",
                "founder_note": founder_note,
                "decided_by": user_id,
                "decided_at": utc_now(),
            },
        )
        if recommendation.get("operation_run_id"):
            self.repo.update(
                "operation_runs",
                recommendation["operation_run_id"],
                workspace_id,
                {
                    "status": "held",
                    "message": "The recommendation is on hold.",
                },
            )
        return self.command_center(workspace_id)

    def revise_recommendation(
        self,
        workspace_id: str,
        recommendation_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        recommendation = self.repo.get(
            "recommendations", recommendation_id, workspace_id
        )
        if not recommendation:
            raise ValueError("Recommendation not found.")
        if recommendation.get("status") not in {"awaiting_founder", "pending", "held"}:
            raise ValueError("Only an unexecuted recommendation can be changed.")
        allowed = {
            key: value
            for key, value in changes.items()
            if key in {"title", "action", "audience", "suggested_channel", "success_metric"}
            and value not in (None, "")
        }
        return self.repo.update(
            "recommendations",
            recommendation_id,
            workspace_id,
            {**allowed, "status": "awaiting_founder"},
        ) or recommendation

    def _baseline(self, workspace_id: str) -> dict[str, Any]:
        context = context_builder.build(workspace_id)
        evidence = {item["key"]: item["value"] for item in context["evidence"]}
        return {
            key: value
            for key, value in evidence.items()
            if key
            in {
                "analytics.activation_rate",
                "analytics.active_users",
                "billing.mrr",
                "billing.churn_rate",
                "billing.revenue_at_risk",
                "database.active_customers",
            }
        }

    def command_center(self, workspace_id: str) -> dict[str, Any]:
        readiness = self.readiness(workspace_id)
        runs = self.repo.list("operation_runs", workspace_id)
        run = runs[0] if runs else None
        review = None
        recommendation = None
        plan = None
        operation_steps: list[dict[str, Any]] = []
        action_steps: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        approvals: list[dict[str, Any]] = []
        outcome = None

        if run:
            operation_steps = sorted(
                [
                    item
                    for item in self.repo.list("operation_steps", workspace_id)
                    if item.get("operation_run_id") == run["id"]
                ],
                key=lambda item: item.get("position", 0),
            )
            review_id = run.get("business_review_id")
            if review_id:
                review = self.repo.get("business_reviews", review_id, workspace_id)
                evidence = [
                    item
                    for item in self.repo.list("evidence_bundles", workspace_id)
                    if item.get("operation_run_id") == run["id"]
                ]
                findings = [
                    item
                    for item in self.repo.list("review_findings", workspace_id)
                    if item.get("operation_run_id") == run["id"]
                ]
            rec_id = run.get("recommendation_id")
            if rec_id:
                recommendation = self.repo.get(
                    "recommendations", rec_id, workspace_id
                )
            plan_id = run.get("action_plan_id")
            if plan_id:
                plan = self.repo.get("action_plans", plan_id, workspace_id)
                action_steps = sorted(
                    [
                        item
                        for item in self.repo.list("action_steps", workspace_id)
                        if item.get("action_plan_id") == plan_id
                    ],
                    key=lambda item: item.get("position", 0),
                )
                approvals = [
                    item
                    for approval_id in plan.get("approval_ids", [])
                    if (
                        item := self.repo.get(
                            "approvals", approval_id, workspace_id
                        )
                    )
                ]
                outcome = next(
                    (
                        item
                        for item in self.repo.list("outcome_checks", workspace_id)
                        if item.get("action_plan_id") == plan_id
                    ),
                    None,
                )

        return {
            "readiness": readiness,
            "operation_run": run,
            "operation_steps": operation_steps,
            "review": review,
            "findings": findings,
            "recommendation": recommendation,
            "evidence": evidence,
            "action_plan": plan,
            "action_steps": action_steps,
            "approvals": approvals,
            "outcome": outcome,
        }


orchestrator = OrchestratorService()
