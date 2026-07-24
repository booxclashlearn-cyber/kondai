from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.core.store import store, utc_now
from app.services.gemini_service import gemini


def _log_run(
    workspace_id: str,
    agent: str,
    action: str,
    result: str,
    metadata: dict[str, Any],
    related: dict[str, Any] | None = None,
) -> dict[str, Any]:
    minutes_saved = {
        "product_analysis": 45,
        "prospect_qualification": 8,
        "outreach_draft": 12,
        "reply_classification": 8,
        "daily_briefing": 20,
        "assistant": 10,
    }.get(action, 5)
    return store.create(
        "agent_runs",
        workspace_id,
        {
            "agent": agent,
            "action": action,
            "result": result,
            "status": "completed",
            "metadata": metadata,
            "related": related or {},
            "estimated_minutes_saved": minutes_saved,
        },
    )


async def analyse_product(workspace_id: str, product: dict[str, Any]) -> dict[str, Any]:
    fallback = {
        "summary": f"{product['name']} is a {product['stage'].replace('_', ' ')} product for an early market.",
        "category": "Software product",
        "core_problem": "The target user needs a faster or simpler way to complete an important workflow.",
        "ideal_customer_profile": product.get("target_customer_assumption")
        or "A clearly defined professional or small team with an urgent recurring problem.",
        "value_proposition": f"{product['name']} helps its ideal users achieve the promised result with less effort.",
        "differentiators": [
            "Focused workflow",
            "Fast onboarding",
            "Designed for early adopters",
        ],
        "likely_objections": [
            "Is the problem urgent enough?",
            "Why use this instead of an existing tool?",
            "Is the product mature and reliable?",
        ],
        "assumptions_to_validate": [
            "The identified user experiences the problem frequently.",
            "The user is willing to try a new solution.",
            "The current value proposition is specific enough.",
        ],
        "launch_readiness_score": 62,
        "next_validation_step": "Interview five target users and run a small personalized outreach campaign.",
    }
    prompt = f"""
Analyse this software product for an early go-to-market campaign.

Product:
{product}

Return one JSON object with exactly these keys:
summary, category, core_problem, ideal_customer_profile, value_proposition,
differentiators, likely_objections, assumptions_to_validate,
launch_readiness_score, next_validation_step.

Do not invent features. Make uncertainty visible.
"""
    result, metadata = await gemini.generate_json(
        "You are a product analyst for solo software founders. Be specific, evidence-based and concise.",
        prompt,
        fallback,
    )
    positioning = store.create(
        "positioning",
        workspace_id,
        {
            "product_id": product["id"],
            "status": "draft",
            "version": len(store.list("positioning", workspace_id)) + 1,
            **result,
        },
    )
    store.update("products", product["id"], workspace_id, {"analysis_status": "completed"})
    _log_run(
        workspace_id,
        "product_analyst",
        "product_analysis",
        "Product analysis and draft positioning created.",
        metadata,
        {"product_id": product["id"], "positioning_id": positioning["id"]},
    )
    return positioning


async def qualify_prospect(
    workspace_id: str,
    prospect: dict[str, Any],
    positioning: dict[str, Any],
) -> dict[str, Any]:
    evidence = " ".join(
        value
        for value in [
            prospect.get("company", ""),
            prospect.get("role", ""),
            prospect.get("website", ""),
            prospect.get("notes", ""),
        ]
        if value
    )
    fallback_score = 50
    if prospect.get("role"):
        fallback_score += 10
    if prospect.get("company"):
        fallback_score += 10
    if prospect.get("notes"):
        fallback_score += 5
    fallback = {
        "fit_score": min(fallback_score, 90),
        "qualification": "possibly_qualified" if fallback_score < 75 else "qualified",
        "reason": (
            f"The record contains enough context to test against the approved profile: "
            f"{positioning.get('ideal_customer_profile', 'target customer')}."
        ),
        "outreach_angle": f"Lead with the problem: {positioning.get('core_problem', 'their current workflow')}.",
        "missing_information": [] if evidence else ["Company, role or relevant need"],
    }
    prompt = f"""
Approved product positioning:
{positioning}

Prospect:
{prospect}

Return JSON with:
fit_score (0-100), qualification (qualified, possibly_qualified,
not_qualified, insufficient_information), reason, outreach_angle,
missing_information.

Use only supplied facts. Do not infer sensitive traits.
"""
    result, metadata = await gemini.generate_json(
        "You qualify prospects for respectful founder-led outreach. Never fabricate facts.",
        prompt,
        fallback,
    )
    updated = store.update(
        "prospects",
        prospect["id"],
        workspace_id,
        {
            "fit_score": int(result.get("fit_score", 0)),
            "qualification": result.get("qualification", "insufficient_information"),
            "qualification_reason": result.get("reason", ""),
            "outreach_angle": result.get("outreach_angle", ""),
            "missing_information": result.get("missing_information", []),
            "qualified_at": utc_now(),
        },
    )
    _log_run(
        workspace_id,
        "prospect_agent",
        "prospect_qualification",
        f"Prospect qualified as {updated.get('qualification') if updated else 'unknown'}.",
        metadata,
        {"prospect_id": prospect["id"]},
    )
    return updated or prospect


async def draft_outreach(
    workspace_id: str,
    product: dict[str, Any],
    positioning: dict[str, Any],
    campaign: dict[str, Any],
    prospect: dict[str, Any],
) -> dict[str, Any]:
    first_name = prospect["name"].split()[0]
    fallback = {
        "subject": f"Quick question about {prospect.get('company') or 'your workflow'}",
        "body": (
            f"Hi {first_name},\n\n"
            f"I’m building {product['name']}, which {positioning.get('value_proposition', 'helps teams improve an important workflow')}.\n\n"
            f"I thought this might be relevant because {prospect.get('role') or 'your work'} appears connected to "
            f"{positioning.get('core_problem', 'the problem we are validating')}.\n\n"
            "Would you be open to a short look and honest feedback? I’m not asking for a long call—"
            "even a brief reply would help us understand whether this is useful.\n\n"
            "Best,\nThe Founder"
        ),
        "personalization_basis": [
            fact for fact in [prospect.get("role"), prospect.get("company"), prospect.get("notes")] if fact
        ],
        "reason": prospect.get("outreach_angle")
        or "The prospect may match the approved ideal customer profile.",
    }
    prompt = f"""
Product:
{product}

Approved positioning:
{positioning}

Campaign:
{campaign}

Prospect:
{prospect}

Create one respectful, concise cold outreach email.
Return JSON with subject, body, personalization_basis, reason.
Do not fabricate familiarity, product usage or private facts.
Do not use deceptive urgency.
"""
    result, metadata = await gemini.generate_json(
        "You write concise, honest founder-to-prospect emails for early product validation.",
        prompt,
        fallback,
        temperature=0.35,
    )
    message = store.create(
        "messages",
        workspace_id,
        {
            "campaign_id": campaign["id"],
            "product_id": product["id"],
            "prospect_id": prospect["id"],
            "recipient": prospect["email"],
            "subject": result.get("subject", fallback["subject"]),
            "body": result.get("body", fallback["body"]),
            "personalization_basis": result.get("personalization_basis", []),
            "reason": result.get("reason", ""),
            "status": "draft",
            "sequence_step": 1,
        },
    )
    approval = store.create(
        "approvals",
        workspace_id,
        {
            "action_type": "send_initial_email",
            "message_id": message["id"],
            "campaign_id": campaign["id"],
            "prospect_id": prospect["id"],
            "subject": message["subject"],
            "body": message["body"],
            "reason": message["reason"],
            "status": "pending",
            "revision": 1,
            "execution_status": "not_started",
        },
    )
    _log_run(
        workspace_id,
        "outreach_agent",
        "outreach_draft",
        "Personalized outreach drafted and submitted for approval.",
        metadata,
        {"message_id": message["id"], "approval_id": approval["id"]},
    )
    return approval


async def classify_reply(workspace_id: str, reply: dict[str, Any]) -> dict[str, Any]:
    body_lower = reply["body"].lower()
    if "unsubscribe" in body_lower or "remove me" in body_lower:
        label = "unsubscribe"
    elif any(word in body_lower for word in ["interested", "yes", "tell me more", "demo"]):
        label = "interested"
    elif any(word in body_lower for word in ["not interested", "no thanks", "no thank"]):
        label = "not_interested"
    elif any(word in body_lower for word in ["later", "not now", "next month"]):
        label = "not_now"
    else:
        label = "unclear"

    fallback = {
        "classification": label,
        "summary": reply["body"][:240],
        "objections": [],
        "feature_requests": [],
        "bugs": [],
        "recommended_next_action": (
            "Stop contact and add to suppression list."
            if label == "unsubscribe"
            else "Founder should review and respond personally."
        ),
    }
    prompt = f"""
Classify this prospect reply:
{reply['body']}

Return JSON with:
classification, summary, objections, feature_requests, bugs,
recommended_next_action.

Allowed classifications:
interested, needs_information, meeting_requested, trial_started, not_now,
not_interested, wrong_person, objection, product_feedback, unsubscribe,
automated_reply, unclear.
"""
    result, metadata = await gemini.generate_json(
        "You classify replies and extract market feedback. Keep facts separate from inference.",
        prompt,
        fallback,
    )
    updated = store.update(
        "replies",
        reply["id"],
        workspace_id,
        {
            "classification": result.get("classification", "unclear"),
            "summary": result.get("summary", ""),
            "objections": result.get("objections", []),
            "feature_requests": result.get("feature_requests", []),
            "bugs": result.get("bugs", []),
            "recommended_next_action": result.get("recommended_next_action", ""),
            "classified_at": utc_now(),
        },
    )
    for objection in result.get("objections", []):
        store.create(
            "feedback",
            workspace_id,
            {
                "reply_id": reply["id"],
                "prospect_id": reply["prospect_id"],
                "type": "objection",
                "content": objection,
            },
        )
    for request in result.get("feature_requests", []):
        store.create(
            "feedback",
            workspace_id,
            {
                "reply_id": reply["id"],
                "prospect_id": reply["prospect_id"],
                "type": "feature_request",
                "content": request,
            },
        )
    _log_run(
        workspace_id,
        "feedback_agent",
        "reply_classification",
        f"Reply classified as {result.get('classification', 'unclear')}.",
        metadata,
        {"reply_id": reply["id"]},
    )
    return updated or reply


async def generate_briefing(workspace_id: str) -> dict[str, Any]:
    products = store.list("products", workspace_id)
    prospects = store.list("prospects", workspace_id)
    campaigns = store.list("campaigns", workspace_id)
    messages = store.list("messages", workspace_id)
    approvals = store.list("approvals", workspace_id)
    replies = store.list("replies", workspace_id)
    feedback = store.list("feedback", workspace_id)
    runs = store.list("agent_runs", workspace_id)

    reply_counts = Counter(reply.get("classification", "unclassified") for reply in replies)
    facts = [
        f"{len(products)} product(s) are in the workspace.",
        f"{len(prospects)} prospect(s) have been added.",
        f"{sum(1 for p in prospects if p.get('qualification') == 'qualified')} prospect(s) are qualified.",
        f"{sum(1 for m in messages if m.get('status') == 'sent')} message(s) have been sent.",
        f"{len(replies)} reply/replies have been recorded.",
    ]
    priorities = []
    pending = sum(1 for approval in approvals if approval.get("status") == "pending")
    if pending:
        priorities.append(f"Review {pending} pending outreach approval(s).")
    unqualified = sum(1 for prospect in prospects if not prospect.get("qualification"))
    if unqualified:
        priorities.append(f"Qualify {unqualified} prospect(s) before campaign preparation.")
    if products and not any(p.get("status") == "approved" for p in store.list("positioning", workspace_id)):
        priorities.append("Approve a positioning version before sending outreach.")
    if not priorities:
        priorities.append("Add new qualified prospects and start the next controlled experiment.")
    priorities = priorities[:3]

    fallback = {
        "headline": "Founder go-to-market briefing",
        "facts": facts,
        "attention": [
            f"{pending} approval(s) need review." if pending else "No pending approvals.",
            f"Reply mix: {dict(reply_counts)}",
        ],
        "recommendations": priorities,
        "feedback_summary": (
            f"{len(feedback)} structured feedback item(s) have been extracted."
        ),
    }
    prompt = f"""
Create a concise daily founder briefing from this verified workspace summary:

products={len(products)}
prospects={len(prospects)}
campaigns={len(campaigns)}
messages={len(messages)}
approvals_pending={pending}
reply_counts={dict(reply_counts)}
feedback_items={len(feedback)}
agent_actions={len(runs)}

Return JSON with headline, facts, attention, recommendations, feedback_summary.
Do not invent metrics.
"""
    result, metadata = await gemini.generate_json(
        "You create evidence-based daily go-to-market briefings for solo founders.",
        prompt,
        fallback,
    )
    briefing = store.create(
        "briefings",
        workspace_id,
        {
            "date": datetime.now(timezone.utc).date().isoformat(),
            **result,
        },
    )
    _log_run(
        workspace_id,
        "briefing_agent",
        "daily_briefing",
        "Daily founder briefing generated.",
        metadata,
        {"briefing_id": briefing["id"]},
    )
    return briefing


async def assistant_response(
    workspace_id: str,
    instruction: str,
    product: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = {
        "products": store.count("products", workspace_id),
        "prospects": store.count("prospects", workspace_id),
        "campaigns": store.count("campaigns", workspace_id),
        "pending_approvals": sum(
            1 for item in store.list("approvals", workspace_id) if item.get("status") == "pending"
        ),
        "replies": store.count("replies", workspace_id),
    }
    fallback = {
        "answer": (
            f"Your workspace has {summary['products']} product(s), {summary['prospects']} prospect(s), "
            f"{summary['campaigns']} campaign(s), {summary['pending_approvals']} pending approval(s), "
            f"and {summary['replies']} recorded reply/replies. "
            "The safest next step is to approve positioning, qualify prospects and prepare a small campaign."
        ),
        "recommended_action": "Review the Today page and complete the highest-priority pending action.",
        "requires_approval": False,
    }
    prompt = f"""
Founder instruction:
{instruction}

Verified workspace summary:
{summary}

Selected product:
{product or 'None'}

Return JSON with answer, recommended_action, requires_approval.
Do not claim that an action was executed.
"""
    result, metadata = await gemini.generate_json(
        "You are an AI go-to-market employee. Give grounded answers using only verified workspace context.",
        prompt,
        fallback,
    )
    _log_run(
        workspace_id,
        "orchestrator",
        "assistant",
        "Founder instruction analysed.",
        metadata,
        {"product_id": product.get("id") if product else None},
    )
    return result
