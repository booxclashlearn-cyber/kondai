from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class SourceType(str, Enum):
    github = "github"
    database = "database"
    billing = "billing"
    analytics = "analytics"
    support = "support"
    market = "market"
    competitor = "competitor"
    product = "product"
    manual = "manual"


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=10, max_length=6000)
    url: str = ""
    category: str = "Software"
    stage: str = "early"
    pricing: str = ""
    target_customer: str = ""
    primary_goal: str = ""

    @field_validator(
        "name", "description", "url", "category", "stage", "pricing",
        "target_customer", "primary_goal", mode="before",
    )
    @classmethod
    def normalise_text(cls, value: Any) -> str:
        return "" if value is None else str(value).strip()


class SourceSnapshotCreate(BaseModel):
    source_type: SourceType
    name: str = Field(min_length=2, max_length=160)
    external_id: str = ""
    product_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class RecommendationDecision(BaseModel):
    status: Literal["approved", "rejected"]
    founder_note: str = ""


class CampaignCreate(BaseModel):
    recommendation_id: str
    name: str = Field(min_length=2, max_length=160)
    channel: Literal[
        "email", "social", "launch", "landing_page", "blog",
        "newsletter", "release_notes",
    ]
    audience: str = Field(min_length=2, max_length=1000)
    goal: str = Field(min_length=2, max_length=1000)


class AssetGenerateRequest(BaseModel):
    asset_type: Literal[
        "email", "social_post", "launch_post", "landing_page",
        "blog_outline", "newsletter", "release_notes",
    ]
    tone: str = "clear, credible and founder-led"


class ApprovalEdit(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=2, max_length=20000)


class SupportTicketCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=160)
    customer_email: EmailStr
    subject: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=2, max_length=20000)
    priority: Literal["low", "medium", "high", "urgent"] = "medium"


class AssistantRequest(BaseModel):
    instruction: str = Field(min_length=2, max_length=4000)


class IntelligenceInsight(BaseModel):
    title: str
    category: Literal["business", "product", "customer", "competitive", "market"]
    severity: Literal["low", "medium", "high", "critical"]
    summary: str
    evidence: list[str] = Field(default_factory=list)


class IntelligenceRecommendation(BaseModel):
    title: str
    priority: Literal["low", "medium", "high", "critical"]
    action: str
    reason: str
    expected_impact: str
    owner_agent: Literal["growth_agent", "support_agent", "founder"]
    confidence: float = Field(ge=0, le=1)


class IntelligenceOutput(BaseModel):
    executive_summary: str
    health_score: int = Field(ge=0, le=100)
    forecast: str
    insights: list[IntelligenceInsight]
    recommendations: list[IntelligenceRecommendation]


class GrowthAssetOutput(BaseModel):
    title: str
    content: str
    call_to_action: str
    grounding_facts: list[str] = Field(default_factory=list)


class SupportDraftOutput(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=1)
    grounding_facts: list[str] = Field(default_factory=list)
    escalation_reason: str = ""
    detected_issue_type: str = "question"


class BriefingOutput(BaseModel):
    greeting: str
    business_snapshot: list[str]
    top_signal: str
    top_risk: str
    recommendation: str
    actions_completed: list[str]
    actions_awaiting_approval: list[str]


class GitHubTokenConnect(BaseModel):
    token: str = Field(min_length=20, max_length=500)


class GitHubRepositoryConnect(BaseModel):
    full_name: str = Field(
        min_length=3,
        max_length=300,
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
    )
    branch: str | None = Field(default=None, max_length=255)


class GitHubPublicRepositoryConnect(BaseModel):
    repository_url: str = Field(min_length=10, max_length=500)


class FirestoreCollections(BaseModel):
    customers: str = Field(default="users", max_length=200)
    accounts: str = Field(default="", max_length=200)
    subscriptions: str = Field(default="", max_length=200)
    events: str = Field(default="", max_length=200)
    documents: str = Field(default="", max_length=200)


class FirestoreConnect(BaseModel):
    service_account: dict[str, Any]
    database_id: str = "(default)"
    collections: FirestoreCollections = Field(default_factory=FirestoreCollections)


class StripeConnect(BaseModel):
    secret_key: str = Field(min_length=20, max_length=500)


class PostHogConnect(BaseModel):
    host: str = Field(default="https://us.posthog.com", min_length=8, max_length=300)
    project_id: str = Field(min_length=1, max_length=100)
    personal_api_key: str = Field(min_length=10, max_length=500)
    activation_event: str = Field(default="", max_length=300)


class GmailSyncRequest(BaseModel):
    query: str = Field(default="", max_length=1000)
    max_messages: int = Field(default=50, ge=1, le=500)


class WhatsAppEmbeddedSignupComplete(BaseModel):
    code: str = Field(min_length=8, max_length=4000)
    waba_id: str = Field(min_length=3, max_length=100)
    phone_number_id: str = Field(min_length=3, max_length=100)
    business_id: str = Field(default="", max_length=100)
    flow_type: str = Field(default="embedded_signup_v4", max_length=100)


class WhatsAppAdvancedConnect(BaseModel):
    access_token: str = Field(min_length=20, max_length=2000)
    phone_number_id: str = Field(min_length=5, max_length=100)
    waba_id: str = Field(min_length=5, max_length=100)
    app_secret: str = Field(min_length=8, max_length=500)
    verify_token: str = Field(min_length=8, max_length=200)
    webhook_base_url: str = Field(min_length=10, max_length=500)


class WhatsAppConversationSend(BaseModel):
    message: str = Field(min_length=1, max_length=4096)


class BusinessReviewFinding(BaseModel):
    title: str
    category: Literal["business", "product", "customer", "growth", "revenue", "evidence"]
    severity: Literal["low", "medium", "high", "critical"]
    summary: str
    why_it_matters: str
    evidence_ids: list[str] = Field(default_factory=list)


class BusinessReviewRecommendation(BaseModel):
    title: str
    objective: str
    action: str
    why_now: str
    expected_impact: str
    confidence: float = Field(ge=0, le=1)
    risk_level: Literal["low", "medium", "high", "restricted"]
    owner_workflow: Literal["growth", "support", "engineering", "founder"]
    suggested_channel: str
    audience: str
    success_metric: str
    time_horizon: str
    alternatives: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class BusinessReviewOutput(BaseModel):
    opening_message: str
    executive_summary: str
    review_scope: list[str]
    data_gaps: list[str]
    findings: list[BusinessReviewFinding]
    recommendation: BusinessReviewRecommendation


class OperationContinueRequest(BaseModel):
    founder_note: str = Field(default="", max_length=2000)


class OperationHoldRequest(BaseModel):
    founder_note: str = Field(default="", max_length=2000)


class RecommendationRevisionRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    action: str | None = Field(default=None, min_length=2, max_length=4000)
    audience: str | None = Field(default=None, min_length=2, max_length=1000)
    suggested_channel: str | None = Field(default=None, max_length=100)
    success_metric: str | None = Field(default=None, min_length=2, max_length=1000)
