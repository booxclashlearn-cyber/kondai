from __future__ import annotations

from typing import Any

from app.core.repository import get_repository, utc_now
from app.services.audit_service import log_agent_run
from app.services.growth_service import growth_service
from app.services.support_service import support_service


class ActionHandoffService:
    """Turns an approved strategic recommendation into reviewable work."""

    def __init__(self) -> None:
        self.repo = get_repository()

    def _update_step(
        self,
        workspace_id: str,
        plan_id: str,
        key: str,
        status: str,
        result: str = "",
    ) -> None:
        step = next(
            (
                item
                for item in self.repo.list("action_steps", workspace_id)
                if item.get("action_plan_id") == plan_id
                and item.get("key") == key
            ),
            None,
        )
        if step:
            self.repo.update(
                "action_steps",
                step["id"],
                workspace_id,
                {
                    "status": status,
                    "result": result,
                    "completed_at": utc_now() if status == "completed" else None,
                },
            )

    async def prepare(
        self,
        workspace_id: str,
        plan_id: str,
    ) -> dict[str, Any]:
        plan = self.repo.get("action_plans", plan_id, workspace_id)
        if not plan:
            raise ValueError("Action plan not found.")
        recommendation = self.repo.get(
            "recommendations", plan["recommendation_id"], workspace_id
        )
        if not recommendation:
            raise ValueError("Recommendation not found.")

        self.repo.update(
            "action_plans",
            plan_id,
            workspace_id,
            {"status": "preparing", "preparation_started_at": utc_now()},
        )
        self._update_step(
            workspace_id,
            plan_id,
            "confirm_scope",
            "completed",
            "The founder approved the recommended direction.",
        )
        self._update_step(
            workspace_id,
            plan_id,
            "select_audience",
            "in_progress",
        )

        workflow = recommendation.get("owner_workflow", "growth")
        deliverables: list[dict[str, Any]] = []
        approval_ids: list[str] = []

        if workflow == "growth":
            channel = recommendation.get("suggested_channel") or "email"
            if channel not in {
                "email",
                "social",
                "launch",
                "landing_page",
                "blog",
                "newsletter",
                "release_notes",
            }:
                channel = "email"
            campaign = growth_service.create_campaign(
                workspace_id,
                recommendation["id"],
                recommendation["title"],
                channel,
                recommendation.get("audience") or "Existing customers",
                recommendation.get("objective") or "Improve customer activity",
            )
            self._update_step(
                workspace_id,
                plan_id,
                "select_audience",
                "completed",
                recommendation.get("audience", "Existing customers"),
            )
            self._update_step(
                workspace_id,
                plan_id,
                "prepare_assets",
                "in_progress",
            )
            asset_type = {
                "social": "social_post",
                "launch": "launch_post",
                "landing_page": "landing_page",
                "blog": "blog_outline",
                "newsletter": "newsletter",
                "release_notes": "release_notes",
            }.get(channel, "email")
            prepared = await growth_service.generate_asset(
                workspace_id,
                campaign["id"],
                asset_type,
                "clear, helpful, credible and specific",
            )
            deliverables.append(
                {
                    "type": "campaign",
                    "id": campaign["id"],
                    "title": campaign["name"],
                    "status": campaign["status"],
                }
            )
            deliverables.append(
                {
                    "type": "growth_asset",
                    "id": prepared["asset"]["id"],
                    "title": prepared["asset"]["title"],
                    "status": prepared["asset"]["status"],
                }
            )
            approval_ids.append(prepared["approval"]["id"])
            self._update_step(
                workspace_id,
                plan_id,
                "prepare_assets",
                "completed",
                f"Prepared a {asset_type.replace('_', ' ')} for review.",
            )
            self._update_step(
                workspace_id,
                plan_id,
                "request_approval",
                "completed",
                "The prepared asset is waiting for final approval.",
            )
        elif workflow == "support":
            self._update_step(
                workspace_id,
                plan_id,
                "select_audience",
                "completed",
                "Open customer issues",
            )
            self._update_step(
                workspace_id,
                plan_id,
                "prepare_assets",
                "in_progress",
            )
            tickets = [
                item
                for item in self.repo.list("support_tickets", workspace_id)
                if item.get("status") in {"open", "escalated"}
            ][:3]
            for ticket in tickets:
                prepared = await support_service.draft_answer(
                    workspace_id, ticket["id"]
                )
                if prepared.get("approval"):
                    approval_ids.append(prepared["approval"]["id"])
                deliverables.append(
                    {
                        "type": "support_draft",
                        "id": prepared.get("draft", {}).get("id"),
                        "title": ticket.get("subject", "Customer response"),
                        "status": "pending_approval"
                        if prepared.get("approval")
                        else "escalated",
                    }
                )
            self._update_step(
                workspace_id,
                plan_id,
                "prepare_assets",
                "completed",
                f"Prepared or escalated {len(deliverables)} customer responses.",
            )
            self._update_step(
                workspace_id,
                plan_id,
                "request_approval",
                "completed",
                "Verified responses are waiting for approval where required.",
            )
        else:
            self._update_step(
                workspace_id,
                plan_id,
                "select_audience",
                "completed",
                recommendation.get("audience", "Founder and product team"),
            )
            self._update_step(
                workspace_id,
                plan_id,
                "prepare_assets",
                "in_progress",
            )
            task = self.repo.create(
                "internal_tasks",
                workspace_id,
                {
                    "title": recommendation["title"],
                    "description": recommendation["action"],
                    "objective": recommendation.get("objective"),
                    "success_metric": recommendation.get("success_metric"),
                    "evidence_ids": recommendation.get("evidence_ids", []),
                    "status": "ready",
                    "owner": "founder_or_engineering",
                    "action_plan_id": plan_id,
                },
            )
            approval = self.repo.create(
                "approvals",
                workspace_id,
                {
                    "action_type": "create_internal_task",
                    "entity_type": "internal_task",
                    "entity_id": task["id"],
                    "title": task["title"],
                    "content": (
                        f"Objective: {task.get('objective', '')}\n\n"
                        f"Task: {task['description']}\n\n"
                        f"Success measure: {task.get('success_metric', '')}"
                    ),
                    "reason": recommendation.get("reason", ""),
                    "status": "pending",
                    "revision": 1,
                    "execution_status": "not_started",
                },
            )
            deliverables.append(
                {
                    "type": "internal_task",
                    "id": task["id"],
                    "title": task["title"],
                    "status": task["status"],
                }
            )
            approval_ids.append(approval["id"])
            self._update_step(
                workspace_id,
                plan_id,
                "prepare_assets",
                "completed",
                "Prepared an evidence-linked internal task.",
            )
            self._update_step(
                workspace_id,
                plan_id,
                "request_approval",
                "completed",
                "The task is waiting for final approval.",
            )

        updated = self.repo.update(
            "action_plans",
            plan_id,
            workspace_id,
            {
                "status": "awaiting_final_approval"
                if approval_ids
                else "prepared",
                "deliverables": deliverables,
                "approval_ids": approval_ids,
                "prepared_at": utc_now(),
            },
        ) or plan
        log_agent_run(
            workspace_id,
            "action_preparation",
            "prepare_approved_next_action",
            (
                f"Prepared {len(deliverables)} deliverables and "
                f"{len(approval_ids)} final approvals."
            ),
            {"mode": "controlled_workflow"},
            {"action_plan_id": plan_id, "approval_ids": approval_ids},
            45,
        )
        return updated


    def mark_execution(
        self,
        workspace_id: str,
        approval_id: str,
        execution_provider: str,
    ) -> None:
        plans = self.repo.list("action_plans", workspace_id)
        for plan in plans:
            if approval_id not in plan.get("approval_ids", []):
                continue
            executed = set(plan.get("executed_approval_ids", []))
            executed.add(approval_id)
            all_approvals = set(plan.get("approval_ids", []))
            status = "executed" if executed >= all_approvals else "partially_executed"
            self.repo.update(
                "action_plans",
                plan["id"],
                workspace_id,
                {
                    "status": status,
                    "executed_approval_ids": sorted(executed),
                    "execution_provider": execution_provider,
                    "executed_at": utc_now() if status == "executed" else None,
                },
            )
            if status == "executed":
                self._update_step(
                    workspace_id,
                    plan["id"],
                    "execute",
                    "completed",
                    f"Approved work executed using {execution_provider}.",
                )
                existing = next(
                    (
                        item
                        for item in self.repo.list("outcome_checks", workspace_id)
                        if item.get("action_plan_id") == plan["id"]
                    ),
                    None,
                )
                if not existing:
                    self.repo.create(
                        "outcome_checks",
                        workspace_id,
                        {
                            "action_plan_id": plan["id"],
                            "recommendation_id": plan["recommendation_id"],
                            "status": "monitoring",
                            "success_metric": plan.get("success_metric"),
                            "time_horizon": plan.get("time_horizon"),
                            "baseline": plan.get("baseline", {}),
                            "latest_result": "Execution completed; outcome monitoring has started.",
                        },
                    )


action_handoff = ActionHandoffService()
