from __future__ import annotations

from typing import Any

from app.core.repository import get_repository, utc_now


class OutcomeTrackerService:
    def __init__(self) -> None:
        self.repo = get_repository()

    def refresh(self, workspace_id: str, plan_id: str) -> dict[str, Any]:
        plan = self.repo.get("action_plans", plan_id, workspace_id)
        if not plan:
            raise ValueError("Action plan not found.")
        checks = [
            item
            for item in self.repo.list("outcome_checks", workspace_id)
            if item.get("action_plan_id") == plan_id
        ]
        check = checks[0] if checks else self.repo.create(
            "outcome_checks",
            workspace_id,
            {
                "action_plan_id": plan_id,
                "recommendation_id": plan["recommendation_id"],
                "status": "monitoring",
                "success_metric": plan.get("success_metric"),
                "time_horizon": plan.get("time_horizon"),
                "baseline": plan.get("baseline", {}),
            },
        )

        approvals = [
            self.repo.get("approvals", approval_id, workspace_id)
            for approval_id in plan.get("approval_ids", [])
        ]
        approvals = [item for item in approvals if item]
        executed = sum(
            1 for item in approvals if item.get("execution_status") == "executed"
        )
        campaigns = [
            item
            for item in self.repo.list("campaigns", workspace_id)
            if item.get("recommendation_id") == plan.get("recommendation_id")
        ]
        resolved_tickets = sum(
            1
            for item in self.repo.list("support_tickets", workspace_id)
            if item.get("status") == "resolved"
        )
        result = {
            "approvals_total": len(approvals),
            "approvals_executed": executed,
            "campaigns_created": len(campaigns),
            "resolved_customer_issues": resolved_tickets,
        }
        status = "monitoring" if executed else "awaiting_execution"
        latest_result = (
            f"{executed} of {len(approvals)} approved actions have executed. "
            "Kondai will compare the connected business metrics with the recorded baseline as new data arrives."
        )
        return self.repo.update(
            "outcome_checks",
            check["id"],
            workspace_id,
            {
                "status": status,
                "latest_result": latest_result,
                "observed": result,
                "checked_at": utc_now(),
            },
        ) or check


outcome_tracker = OutcomeTrackerService()
