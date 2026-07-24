from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.repository import get_repository, utc_now
from app.services.audit_service import log_agent_run


class ApprovalService:
    def __init__(self) -> None:
        self.repo = get_repository()

    def decide(
        self,
        workspace_id: str,
        approval_id: str,
        status: str,
        user_id: str,
    ) -> dict[str, Any]:
        approval = self.repo.get("approvals", approval_id, workspace_id)
        if not approval:
            raise ValueError("Approval not found.")
        if approval.get("status") == status:
            return approval
        if approval.get("status") != "pending":
            raise ValueError("Only pending approvals can be changed.")
        return self.repo.update(
            "approvals",
            approval_id,
            workspace_id,
            {
                "status": status,
                "decided_by": user_id,
                "decided_at": utc_now(),
            },
        ) or approval

    def edit(
        self,
        workspace_id: str,
        approval_id: str,
        title: str,
        content: str,
        user_id: str,
    ) -> dict[str, Any]:
        approval = self.repo.get("approvals", approval_id, workspace_id)
        if not approval:
            raise ValueError("Approval not found.")
        if approval.get("status") != "pending":
            raise ValueError("Only pending approvals can be edited.")
        return self.repo.update(
            "approvals",
            approval_id,
            workspace_id,
            {
                "title": title,
                "content": content,
                "edited_by": user_id,
                "revision": int(approval.get("revision", 1)) + 1,
            },
        ) or approval

    def execute(self, workspace_id: str, approval_id: str) -> dict[str, Any]:
        approval = self.repo.get("approvals", approval_id, workspace_id)
        if not approval:
            raise ValueError("Approval not found.")
        if approval.get("execution_status") == "executed":
            return approval
        if approval.get("status") != "approved":
            raise ValueError("Approve the action before execution.")

        today = datetime.now(timezone.utc).date().isoformat()
        executions = [
            item
            for item in self.repo.list("approvals", workspace_id)
            if item.get("execution_status") == "executed"
            and str(item.get("executed_at", "")).startswith(today)
        ]
        if len(executions) >= get_settings().max_daily_executions:
            raise ValueError("Daily execution limit reached.")

        action = approval.get("action_type")
        entity_id = approval.get("entity_id")
        execution_provider = get_settings().outbound_mode
        provider_message_id = None

        if action == "publish_growth_asset":
            self.repo.update(
                "growth_assets",
                entity_id,
                workspace_id,
                {
                    "status": "executed_mock",
                    "executed_content": approval["content"],
                },
            )
        elif action == "create_internal_task":
            task = self.repo.get("internal_tasks", entity_id, workspace_id)
            if task:
                self.repo.update(
                    "internal_tasks",
                    entity_id,
                    workspace_id,
                    {
                        "status": "active",
                        "approved_content": approval["content"],
                        "activated_at": utc_now(),
                    },
                )
            execution_provider = "internal_task_queue"
        elif action == "send_support_reply":
            draft = self.repo.get("support_drafts", entity_id, workspace_id)
            if draft:
                ticket = self.repo.get(
                    "support_tickets", draft["ticket_id"], workspace_id
                )
                if ticket and ticket.get("channel") == "whatsapp":
                    from app.services.whatsapp_integration_service import (
                        whatsapp_integration,
                    )

                    conversation_id = ticket.get("external_conversation_id")
                    if not conversation_id:
                        raise ValueError(
                            "The WhatsApp ticket is missing its conversation."
                        )
                    sent = whatsapp_integration.send_text(
                        workspace_id, conversation_id, approval["content"]
                    )
                    execution_provider = "whatsapp_cloud_api"
                    provider_message_id = sent.get("external_message_id")
                    draft_status = "sent"
                else:
                    draft_status = "sent_mock"

                self.repo.update(
                    "support_drafts",
                    entity_id,
                    workspace_id,
                    {
                        "status": draft_status,
                        "sent_content": approval["content"],
                        "provider_message_id": provider_message_id,
                    },
                )
                self.repo.update(
                    "support_tickets",
                    draft["ticket_id"],
                    workspace_id,
                    {"status": "resolved", "resolved_at": utc_now()},
                )

        updated = self.repo.update(
            "approvals",
            approval_id,
            workspace_id,
            {
                "execution_status": "executed",
                "executed_at": utc_now(),
                "execution_provider": execution_provider,
                "provider_message_id": provider_message_id,
            },
        ) or approval
        log_agent_run(
            workspace_id,
            "controlled_executor",
            action or "execution",
            f"Executed approved action using {execution_provider}.",
            {"mode": execution_provider},
            {"approval_id": approval_id},
            5,
        )
        from app.services.action_handoff_service import action_handoff

        action_handoff.mark_execution(
            workspace_id,
            approval_id,
            execution_provider,
        )
        return updated


approval_service = ApprovalService()
