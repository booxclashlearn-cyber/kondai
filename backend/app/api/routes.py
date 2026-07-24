from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, RedirectResponse

from app.core.auth import Actor, get_actor
from app.core.config import get_settings
from app.core.repository import get_repository, utc_now
from app.models.schemas import (
    ApprovalEdit,
    AssetGenerateRequest,
    AssistantRequest,
    CampaignCreate,
    FirestoreConnect,
    GitHubPublicRepositoryConnect,
    GitHubRepositoryConnect,
    GitHubTokenConnect,
    GmailSyncRequest,
    PostHogConnect,
    ProductCreate,
    RecommendationDecision,
    RecommendationRevisionRequest,
    OperationContinueRequest,
    OperationHoldRequest,
    SourceSnapshotCreate,
    StripeConnect,
    SupportTicketCreate,
    WhatsAppAdvancedConnect,
    WhatsAppEmbeddedSignupComplete,
    WhatsAppConversationSend,
)
from app.services.approval_service import approval_service
from app.services.assistant_service import answer_founder
from app.services.briefing_service import briefing_service
from app.services.firestore_integration_service import firestore_integration
from app.services.founder_intelligence_service import founder_intelligence
from app.services.github_service import github_service
from app.services.gmail_integration_service import gmail_integration
from app.services.growth_service import growth_service
from app.services.knowledge_graph_service import knowledge_graph
from app.services.orchestrator_service import orchestrator
from app.services.outcome_tracker_service import outcome_tracker
from app.services.posthog_integration_service import posthog_integration
from app.services.stripe_integration_service import stripe_integration
from app.services.support_service import support_service
from app.services.whatsapp_integration_service import whatsapp_integration

router = APIRouter()
repo = get_repository()


def require_record(collection: str, record_id: str, actor: Actor) -> dict[str, Any]:
    record = repo.get(collection, record_id, actor.workspace_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"{collection} record not found.")
    return record


@router.get("/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "ai_mode": settings.ai_mode,
        "store_mode": settings.store_mode,
        "outbound_mode": settings.outbound_mode,
        "timestamp": utc_now(),
    }


@router.get("/me")
async def me(actor: Actor = Depends(get_actor)) -> dict[str, str]:
    return {
        "user_id": actor.user_id,
        "workspace_id": actor.workspace_id,
        "role": actor.role,
    }


@router.get("/dashboard")
async def dashboard(actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    intelligence = repo.list("intelligence_runs", actor.workspace_id)
    briefings = repo.list("briefings", actor.workspace_id)
    recommendations = repo.list("recommendations", actor.workspace_id)
    approvals = repo.list("approvals", actor.workspace_id)
    tickets = repo.list("support_tickets", actor.workspace_id)
    campaigns = repo.list("campaigns", actor.workspace_id)
    nodes = repo.list("knowledge_nodes", actor.workspace_id)
    runs = repo.list("agent_runs", actor.workspace_id)
    return {
        "health_score": intelligence[0].get("health_score") if intelligence else None,
        "latest_intelligence": intelligence[0] if intelligence else None,
        "latest_briefing": briefings[0] if briefings else None,
        "counts": {
            "knowledge_facts": sum(1 for node in nodes if node.get("node_type") == "fact"),
            "pending_recommendations": sum(1 for item in recommendations if item.get("status") == "pending"),
            "approved_recommendations": sum(1 for item in recommendations if item.get("status") == "approved"),
            "campaigns": len(campaigns),
            "pending_approvals": sum(1 for item in approvals if item.get("status") == "pending"),
            "open_support_tickets": sum(1 for item in tickets if item.get("status") in {"open", "escalated"}),
        },
        "recent_activity": runs[:6],
    }


@router.get("/products")
async def list_products(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("products", actor.workspace_id)


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    return repo.create("products", actor.workspace_id, payload.model_dump())


@router.get("/sources")
async def list_sources(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("sources", actor.workspace_id)


@router.post("/sources", status_code=status.HTTP_201_CREATED)
async def ingest_source(payload: SourceSnapshotCreate, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    if payload.product_id:
        require_record("products", payload.product_id, actor)
    return knowledge_graph.ingest(
        actor.workspace_id,
        payload.source_type.value,
        payload.name,
        payload.data,
        payload.external_id,
        payload.product_id,
    )


@router.get("/knowledge-graph")
async def graph(actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    return knowledge_graph.graph(actor.workspace_id)


@router.post("/intelligence/run")
async def run_intelligence(actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    return await founder_intelligence.run(actor.workspace_id)


@router.get("/intelligence/runs")
async def intelligence_runs(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("intelligence_runs", actor.workspace_id)


@router.get("/insights")
async def insights(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("insights", actor.workspace_id)


@router.get("/recommendations")
async def recommendations(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("recommendations", actor.workspace_id)


@router.post("/recommendations/{recommendation_id}/decision")
async def decide_recommendation(
    recommendation_id: str,
    payload: RecommendationDecision,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    recommendation = require_record("recommendations", recommendation_id, actor)
    if recommendation.get("status") not in {"pending", payload.status}:
        raise HTTPException(status_code=409, detail="Recommendation has already been decided.")
    return repo.update(
        "recommendations",
        recommendation_id,
        actor.workspace_id,
        {
            "status": payload.status,
            "founder_note": payload.founder_note,
            "decided_by": actor.user_id,
            "decided_at": utc_now(),
        },
    ) or recommendation


@router.get("/growth/campaigns")
async def campaigns(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("campaigns", actor.workspace_id)


@router.post("/growth/campaigns", status_code=status.HTTP_201_CREATED)
async def create_campaign(payload: CampaignCreate, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        return growth_service.create_campaign(
            actor.workspace_id,
            payload.recommendation_id,
            payload.name,
            payload.channel,
            payload.audience,
            payload.goal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/growth/campaigns/{campaign_id}/assets")
async def generate_asset(
    campaign_id: str,
    payload: AssetGenerateRequest,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    try:
        return await growth_service.generate_asset(
            actor.workspace_id, campaign_id, payload.asset_type, payload.tone
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/growth/assets")
async def assets(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("growth_assets", actor.workspace_id)


@router.get("/support/tickets")
async def tickets(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("support_tickets", actor.workspace_id)


@router.post("/support/tickets", status_code=status.HTTP_201_CREATED)
async def create_ticket(payload: SupportTicketCreate, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    return support_service.create_ticket(actor.workspace_id, payload.model_dump(mode="json"))


@router.post("/support/tickets/{ticket_id}/draft")
async def draft_ticket(ticket_id: str, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        return await support_service.draft_answer(actor.workspace_id, ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/support/drafts")
async def drafts(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("support_drafts", actor.workspace_id)


@router.get("/feedback")
async def feedback(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("feedback_items", actor.workspace_id)


@router.get("/approvals")
async def approvals(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("approvals", actor.workspace_id)


@router.patch("/approvals/{approval_id}")
async def edit_approval(
    approval_id: str,
    payload: ApprovalEdit,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    try:
        return approval_service.edit(
            actor.workspace_id, approval_id, payload.title, payload.content, actor.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/approve")
async def approve(approval_id: str, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        return approval_service.decide(actor.workspace_id, approval_id, "approved", actor.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/reject")
async def reject(approval_id: str, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        return approval_service.decide(actor.workspace_id, approval_id, "rejected", actor.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/execute")
async def execute(approval_id: str, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        return approval_service.execute(actor.workspace_id, approval_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/briefings/generate")
async def generate_briefing(actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    return await briefing_service.generate(actor.workspace_id)


@router.get("/briefings/today")
async def today(actor: Actor = Depends(get_actor)) -> dict[str, Any] | None:
    items = repo.list("briefings", actor.workspace_id)
    return items[0] if items else None


@router.get("/agent-activity")
async def activity(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    return repo.list("agent_runs", actor.workspace_id)


@router.get("/operations/command-center")
async def operations_command_center(
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    return orchestrator.command_center(actor.workspace_id)


@router.get("/operations/readiness")
async def operations_readiness(
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    return orchestrator.readiness(actor.workspace_id)


@router.post("/operations/initial-review")
async def operations_initial_review(
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    try:
        await orchestrator.maybe_start_review(
            actor.workspace_id,
            trigger="founder_requested_review",
            force=True,
        )
        return orchestrator.command_center(actor.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/operations/runs/{run_id}")
async def operations_run(
    run_id: str,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    run = require_record("operation_runs", run_id, actor)
    steps = sorted(
        [
            item
            for item in repo.list("operation_steps", actor.workspace_id)
            if item.get("operation_run_id") == run_id
        ],
        key=lambda item: item.get("position", 0),
    )
    return {"run": run, "steps": steps}


@router.get("/operations/latest-review")
async def operations_latest_review(
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    return orchestrator.command_center(actor.workspace_id)


@router.post("/operations/recommendations/{recommendation_id}/continue")
async def operations_continue(
    recommendation_id: str,
    payload: OperationContinueRequest,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    try:
        return await orchestrator.continue_recommendation(
            actor.workspace_id,
            recommendation_id,
            actor.user_id,
            payload.founder_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/operations/recommendations/{recommendation_id}/hold")
async def operations_hold(
    recommendation_id: str,
    payload: OperationHoldRequest,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    try:
        return orchestrator.hold_recommendation(
            actor.workspace_id,
            recommendation_id,
            actor.user_id,
            payload.founder_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/operations/recommendations/{recommendation_id}")
async def operations_revise(
    recommendation_id: str,
    payload: RecommendationRevisionRequest,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    try:
        orchestrator.revise_recommendation(
            actor.workspace_id,
            recommendation_id,
            payload.model_dump(exclude_none=True),
        )
        return orchestrator.command_center(actor.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/operations/plans/{plan_id}/outcome/refresh")
async def operations_refresh_outcome(
    plan_id: str,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    try:
        outcome_tracker.refresh(actor.workspace_id, plan_id)
        return orchestrator.command_center(actor.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/onboarding/status")
async def onboarding_status(actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    return github_service.onboarding_status(actor.workspace_id)


@router.get("/integrations")
async def integrations(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    github = github_service.public_status(actor.workspace_id)
    database = firestore_integration.status(actor.workspace_id)
    billing = stripe_integration.status(actor.workspace_id)
    analytics = posthog_integration.status(actor.workspace_id)
    support = gmail_integration.status(actor.workspace_id)
    whatsapp = whatsapp_integration.status(actor.workspace_id)
    return [
        {
            "key": "github",
            "name": "GitHub",
            "status": github["status"],
            "mode": "live",
            "description": (
                f"Reading {github.get('selected_repository')}"
                if github.get("repository_connected")
                else "Connect the codebase Kondai should understand."
            ),
            "details": github,
            "available": True,
        },
        {
            "key": "firestore",
            "name": "Product Database",
            "status": database["status"],
            "mode": "live",
            "description": (
                f"Reading Firestore project {database.get('project_id')}"
                if database.get("connected")
                else "Connect customer, account and product records from Firestore."
            ),
            "details": database,
            "available": True,
        },
        {
            "key": "stripe",
            "name": "Stripe / Billing",
            "status": billing["status"],
            "mode": "live",
            "description": (
                f"Reading Stripe account {billing.get('account_id')}"
                if billing.get("connected")
                else "Connect subscriptions, revenue, retention and payment risk."
            ),
            "details": billing,
            "available": True,
        },
        {
            "key": "posthog",
            "name": "Product Analytics",
            "status": analytics["status"],
            "mode": "live",
            "description": (
                f"Reading PostHog project {analytics.get('project_id')}"
                if analytics.get("connected")
                else "Connect usage, activation and feature adoption from PostHog."
            ),
            "details": analytics,
            "available": True,
        },
        {
            "key": "gmail",
            "name": "Support Inbox",
            "status": support["status"],
            "mode": "live",
            "description": (
                f"Reading customer mail from {support.get('email_address')}"
                if support.get("connected")
                else "Connect Gmail to import customer questions and support signals."
            ),
            "details": support,
            "available": True,
        },
        {
            "key": "whatsapp",
            "name": "WhatsApp",
            "status": whatsapp["status"],
            "mode": "live",
            "description": (
                f"Receiving chats for {whatsapp.get('display_phone_number')}"
                if whatsapp.get("connected")
                else "Connect a WhatsApp Business number to receive customer chats."
            ),
            "details": whatsapp,
            "available": True,
        },
    ]


# GitHub
@router.post("/integrations/github/oauth/start")
async def github_oauth_start(actor: Actor = Depends(get_actor)) -> dict[str, str]:
    try:
        return github_service.start_oauth(actor.workspace_id, actor.user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/integrations/github/oauth/callback", include_in_schema=False)
async def github_oauth_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    settings = get_settings()
    if error:
        return RedirectResponse(f"{settings.frontend_url}/setup?github=error&message={quote(error_description or error)}")
    try:
        await github_service.complete_oauth(code, state)
        return RedirectResponse(f"{settings.frontend_url}/setup?github=connected")
    except Exception as exc:
        return RedirectResponse(f"{settings.frontend_url}/setup?github=error&message={quote(str(exc))}")


@router.post("/integrations/github/token")
async def github_token_connect(payload: GitHubTokenConnect, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        return await github_service.connect_token(actor.workspace_id, actor.user_id, payload.token)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/integrations/github/repositories")
async def github_repositories(actor: Actor = Depends(get_actor)) -> list[dict[str, Any]]:
    try:
        return await github_service.list_repositories(actor.workspace_id)
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/integrations/github/repositories/connect")
async def github_repository_connect(payload: GitHubRepositoryConnect, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        integration = await github_service.sync_repository(
            actor.workspace_id, actor.user_id, payload.full_name, payload.branch
        )
        operation = await orchestrator.maybe_start_review(
            actor.workspace_id, trigger="github_repository_connected"
        )
        return {**integration, "operation": operation}
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/integrations/github/public-repository")
async def github_public_repository(payload: GitHubPublicRepositoryConnect, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        integration = await github_service.connect_public_repository(
            actor.workspace_id, actor.user_id, payload.repository_url
        )
        operation = await orchestrator.maybe_start_review(
            actor.workspace_id, trigger="github_repository_connected"
        )
        return {**integration, "operation": operation}
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/integrations/github")
async def github_disconnect(actor: Actor = Depends(get_actor)) -> dict[str, bool]:
    return {"disconnected": github_service.disconnect(actor.workspace_id)}


# Firestore
@router.post("/integrations/firestore/connect")
async def firestore_connect(payload: FirestoreConnect, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        integration = firestore_integration.connect(
            actor.workspace_id,
            actor.user_id,
            payload.service_account,
            payload.database_id,
            payload.collections.model_dump(),
        )
        operation = await orchestrator.maybe_start_review(
            actor.workspace_id, trigger="product_database_connected"
        )
        return {"integration": integration, "operation": operation}
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/integrations/firestore/sync")
async def firestore_sync(actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        integration = firestore_integration.sync(actor.workspace_id)
        operation = await orchestrator.maybe_start_review(
            actor.workspace_id, trigger="product_database_refreshed", force=True
        )
        return {"integration": integration, "operation": operation}
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/integrations/firestore")
async def firestore_disconnect(actor: Actor = Depends(get_actor)) -> dict[str, bool]:
    return {"disconnected": firestore_integration.disconnect(actor.workspace_id)}


# Stripe
@router.post("/integrations/stripe/connect")
async def stripe_connect(payload: StripeConnect, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        integration = await stripe_integration.connect(
            actor.workspace_id, actor.user_id, payload.secret_key
        )
        operation = await orchestrator.maybe_start_review(
            actor.workspace_id, trigger="billing_connected", force=True
        )
        return {"integration": integration, "operation": operation}
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/integrations/stripe/sync")
async def stripe_sync(actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        integration = await stripe_integration.sync(actor.workspace_id)
        operation = await orchestrator.maybe_start_review(
            actor.workspace_id, trigger="billing_refreshed", force=True
        )
        return {"integration": integration, "operation": operation}
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/integrations/stripe")
async def stripe_disconnect(actor: Actor = Depends(get_actor)) -> dict[str, bool]:
    return {"disconnected": stripe_integration.disconnect(actor.workspace_id)}


# PostHog
@router.post("/integrations/posthog/connect")
async def posthog_connect(payload: PostHogConnect, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        integration = await posthog_integration.connect(
            actor.workspace_id,
            actor.user_id,
            payload.host,
            payload.project_id,
            payload.personal_api_key,
            payload.activation_event,
        )
        operation = await orchestrator.maybe_start_review(
            actor.workspace_id, trigger="analytics_connected", force=True
        )
        return {"integration": integration, "operation": operation}
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/integrations/posthog/sync")
async def posthog_sync(actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        integration = await posthog_integration.sync(actor.workspace_id)
        operation = await orchestrator.maybe_start_review(
            actor.workspace_id, trigger="analytics_refreshed", force=True
        )
        return {"integration": integration, "operation": operation}
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/integrations/posthog")
async def posthog_disconnect(actor: Actor = Depends(get_actor)) -> dict[str, bool]:
    return {"disconnected": posthog_integration.disconnect(actor.workspace_id)}


# Gmail
@router.post("/integrations/gmail/oauth/start")
async def gmail_oauth_start(actor: Actor = Depends(get_actor)) -> dict[str, str]:
    try:
        return gmail_integration.start_oauth(actor.workspace_id, actor.user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/integrations/gmail/oauth/callback", include_in_schema=False)
async def gmail_oauth_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    settings = get_settings()
    if error:
        return RedirectResponse(f"{settings.frontend_url}/integrations?gmail=error&message={quote(error_description or error)}")
    try:
        await gmail_integration.complete_oauth(code, state)
        return RedirectResponse(f"{settings.frontend_url}/integrations?gmail=connected")
    except Exception as exc:
        return RedirectResponse(f"{settings.frontend_url}/integrations?gmail=error&message={quote(str(exc))}")


@router.post("/integrations/gmail/sync")
async def gmail_sync(payload: GmailSyncRequest, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        return await gmail_integration.sync(
            actor.workspace_id, payload.query, payload.max_messages
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/integrations/gmail")
async def gmail_disconnect(actor: Actor = Depends(get_actor)) -> dict[str, bool]:
    return {"disconnected": gmail_integration.disconnect(actor.workspace_id)}


# WhatsApp Business Platform
@router.get("/integrations/whatsapp/embedded/config")
async def whatsapp_embedded_config(
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    return whatsapp_integration.embedded_signup_config()


@router.post("/integrations/whatsapp/embedded/complete")
async def whatsapp_embedded_complete(
    payload: WhatsAppEmbeddedSignupComplete,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    try:
        return await whatsapp_integration.complete_embedded_signup(
            actor.workspace_id,
            actor.user_id,
            payload.code,
            payload.waba_id,
            payload.phone_number_id,
            payload.business_id,
            payload.flow_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/integrations/whatsapp/advanced/connect",
    include_in_schema=False,
)
async def whatsapp_advanced_connect(
    payload: WhatsAppAdvancedConnect,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    try:
        return await whatsapp_integration.connect(
            actor.workspace_id,
            actor.user_id,
            payload.access_token,
            payload.phone_number_id,
            payload.waba_id,
            payload.app_secret,
            payload.verify_token,
            payload.webhook_base_url,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/integrations/whatsapp/sync")
async def whatsapp_sync(actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    try:
        return whatsapp_integration.sync(actor.workspace_id)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/integrations/whatsapp/conversations")
async def whatsapp_conversations(
    actor: Actor = Depends(get_actor),
) -> list[dict[str, Any]]:
    return whatsapp_integration.conversations(actor.workspace_id)


@router.get("/integrations/whatsapp/conversations/{conversation_id}/messages")
async def whatsapp_messages(
    conversation_id: str,
    actor: Actor = Depends(get_actor),
) -> list[dict[str, Any]]:
    return whatsapp_integration.messages(actor.workspace_id, conversation_id)


@router.post("/integrations/whatsapp/conversations/{conversation_id}/mark-read")
async def whatsapp_mark_read(
    conversation_id: str,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    try:
        return whatsapp_integration.mark_read(actor.workspace_id, conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/integrations/whatsapp/conversations/{conversation_id}/send")
async def whatsapp_send(
    conversation_id: str,
    payload: WhatsAppConversationSend,
    actor: Actor = Depends(get_actor),
) -> dict[str, Any]:
    raise HTTPException(
        status_code=409,
        detail=(
            "Direct sending is disabled. Prepare a verified response from "
            "Customer Care and approve it before execution."
        ),
    )


@router.delete("/integrations/whatsapp")
async def whatsapp_disconnect(actor: Actor = Depends(get_actor)) -> dict[str, bool]:
    return {"disconnected": whatsapp_integration.disconnect(actor.workspace_id)}


@router.get(
    "/integrations/whatsapp/webhook",
    include_in_schema=False,
)
async def whatsapp_global_webhook_verify(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    try:
        challenge = whatsapp_integration.verify_global_webhook(
            hub_mode, hub_verify_token, hub_challenge
        )
        return PlainTextResponse(challenge, status_code=200)
    except Exception as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/integrations/whatsapp/webhook",
    include_in_schema=False,
)
async def whatsapp_global_webhook_receive(
    request: Request,
) -> dict[str, Any]:
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    try:
        result = whatsapp_integration.receive_global_webhook(
            raw_body, signature
        )
        return {"status": "ok", **result}
    except Exception as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/integrations/whatsapp/webhook/{workspace_token}/{webhook_key}",
    include_in_schema=False,
)
async def whatsapp_webhook_verify(
    workspace_token: str,
    webhook_key: str,
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    try:
        challenge = whatsapp_integration.verify_webhook(
            workspace_token,
            webhook_key,
            hub_mode,
            hub_verify_token,
            hub_challenge,
        )
        return PlainTextResponse(challenge, status_code=200)
    except Exception as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/integrations/whatsapp/webhook/{workspace_token}/{webhook_key}",
    include_in_schema=False,
)
async def whatsapp_webhook_receive(
    workspace_token: str,
    webhook_key: str,
    request: Request,
) -> dict[str, Any]:
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    try:
        result = whatsapp_integration.receive_webhook(
            workspace_token,
            webhook_key,
            raw_body,
            signature,
        )
        return {"status": "ok", **result}
    except Exception as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/assistant/chat")
async def assistant(payload: AssistantRequest, actor: Actor = Depends(get_actor)) -> dict[str, Any]:
    return answer_founder(actor.workspace_id, payload.instruction)
