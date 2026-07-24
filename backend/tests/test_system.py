import os
from pathlib import Path

os.environ["AUTH_MODE"] = "dev"
os.environ["AI_MODE"] = "demo"
os.environ["STORE_MODE"] = "json"
os.environ["JSON_STORE_PATH"] = "data/test-store.json"
os.environ["INTEGRATION_ENCRYPTION_KEY"] = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
os.environ["META_APP_ID"] = "1234567890"
os.environ["META_APP_SECRET"] = "test-meta-app-secret"
os.environ["META_EMBEDDED_SIGNUP_CONFIG_ID"] = "test-config-id"
os.environ["META_WEBHOOK_VERIFY_TOKEN"] = "test-platform-verify-token"
os.environ["PUBLIC_API_BASE_URL"] = "https://api.example.com"

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.repository import get_repository
from app.main import app


get_settings.cache_clear()
get_repository.cache_clear()

client = TestClient(app)
headers = {
    "X-User-Id": "test-founder",
    "X-Workspace-Id": "test-workspace",
}


def setup_module():
    path = Path("data/test-store.json")
    if path.exists():
        path.unlink()
    get_repository.cache_clear()


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_first_run_requires_codebase_connection():
    response = client.get("/api/v1/onboarding/status", headers=headers)
    assert response.status_code == 200
    assert response.json()["complete"] is False
    assert response.json()["current_step"] == "connect_codebase"

    integrations = client.get("/api/v1/integrations", headers=headers)
    assert integrations.status_code == 200
    github = next(
        item for item in integrations.json() if item["key"] == "github"
    )
    assert github["status"] == "not_connected"


def test_closed_loop_vertical_slice():
    product = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Production SaaS",
            "description": "A real SaaS product used to validate business operations.",
            "url": "https://example.com",
            "category": "SaaS",
            "stage": "early_revenue",
            "pricing": "$39/month",
            "target_customer": "Small software businesses",
            "primary_goal": "Improve activation and retention",
        },
    )
    assert product.status_code == 201
    product_id = product.json()["id"]

    snapshots = [
        {
            "source_type": "billing",
            "name": "Billing snapshot",
            "product_id": product_id,
            "data": {
                "currency": "USD",
                "mrr": 1420,
                "arr": 17040,
                "active_customers": 38,
                "churn_rate": 18,
                "retention_rate": 82,
                "revenue_at_risk": 117,
            },
        },
        {
            "source_type": "analytics",
            "name": "Analytics snapshot",
            "product_id": product_id,
            "data": {
                "active_users": 64,
                "activation_rate": 24,
                "dormant_paid_users": 6,
                "documents_last_30_days": 52,
                "feature_usage": {"Core workflow": 92},
            },
        },
        {
            "source_type": "support",
            "name": "Support snapshot",
            "product_id": product_id,
            "data": {
                "open_tickets": 3,
                "satisfaction": 78,
                "themes": [{"name": "Onboarding difficulty", "count": 5}],
            },
        },
    ]

    for snapshot in snapshots:
        response = client.post("/api/v1/sources", headers=headers, json=snapshot)
        assert response.status_code == 201

    graph = client.get("/api/v1/knowledge-graph", headers=headers)
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) > 5

    intelligence = client.post("/api/v1/intelligence/run", headers=headers)
    assert intelligence.status_code == 200
    assert intelligence.json()["health_score"] >= 0

    recommendations = client.get(
        "/api/v1/recommendations",
        headers=headers,
    ).json()
    assert recommendations

    approved = client.post(
        f"/api/v1/recommendations/{recommendations[0]['id']}/decision",
        headers=headers,
        json={
            "status": "approved",
            "founder_note": "Proceed with a controlled test.",
        },
    )
    assert approved.status_code == 200

    campaign = client.post(
        "/api/v1/growth/campaigns",
        headers=headers,
        json={
            "recommendation_id": recommendations[0]["id"],
            "name": "Priority growth experiment",
            "channel": "email",
            "audience": "Existing customers",
            "goal": "Improve activation or retention",
        },
    )
    assert campaign.status_code == 201

    asset = client.post(
        f"/api/v1/growth/campaigns/{campaign.json()['id']}/assets",
        headers=headers,
        json={"asset_type": "email", "tone": "clear and helpful"},
    )
    assert asset.status_code == 200
    approval_id = asset.json()["approval"]["id"]

    assert client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers=headers,
    ).status_code == 200
    executed = client.post(
        f"/api/v1/approvals/{approval_id}/execute",
        headers=headers,
    )
    assert executed.status_code == 200
    assert executed.json()["execution_status"] == "executed"

    ticket = client.post(
        "/api/v1/support/tickets",
        headers=headers,
        json={
            "customer_name": "Test Customer",
            "customer_email": "customer@example.com",
            "subject": "Where do I start?",
            "message": "My account is active but onboarding is unclear.",
            "priority": "high",
        },
    )
    assert ticket.status_code == 201

    support = client.post(
        f"/api/v1/support/tickets/{ticket.json()['id']}/draft",
        headers=headers,
    )
    assert support.status_code == 200

    briefing = client.post("/api/v1/briefings/generate", headers=headers)
    assert briefing.status_code == 200
    assert briefing.json()["recommendation"]



def test_all_live_connectors_are_available_but_honest():
    response = client.get("/api/v1/integrations", headers=headers)
    assert response.status_code == 200
    by_key = {item["key"]: item for item in response.json()}
    for key in ("firestore", "stripe", "posthog", "gmail", "whatsapp"):
        assert by_key[key]["available"] is True
        assert by_key[key]["status"] == "not_connected"


def test_stripe_monthly_value_normalisation():
    from app.services.stripe_integration_service import StripeIntegrationService

    monthly = {
        "items": {"data": [{"quantity": 2, "price": {
            "unit_amount": 3900,
            "recurring": {"interval": "month", "interval_count": 1},
        }}]}
    }
    annual = {
        "items": {"data": [{"quantity": 1, "price": {
            "unit_amount": 12000,
            "recurring": {"interval": "year", "interval_count": 1},
        }}]}
    }
    assert StripeIntegrationService.monthly_value(monthly) == 78
    assert StripeIntegrationService.monthly_value(annual) == 10



def test_whatsapp_webhook_creates_conversation():
    import base64
    import hashlib
    import hmac
    import json

    from app.services.integration_utils import integration_store
    from app.services.secret_service import secret_service

    workspace_id = headers["X-Workspace-Id"]
    webhook_key = "test-webhook-key"
    verify_token = "verify-token-123"
    app_secret = "app-secret-123"

    integration_store.save(
        workspace_id,
        "whatsapp",
        {
            "status": "connected",
            "connection_type": "meta_cloud_api",
            "encrypted_access_token": secret_service.encrypt(
                "test-access-token-1234567890"
            ),
            "encrypted_app_secret": secret_service.encrypt(app_secret),
            "encrypted_verify_token": secret_service.encrypt(verify_token),
            "phone_number_id": "123456789",
            "waba_id": "987654321",
            "webhook_key": webhook_key,
            "callback_url": "https://example.com/webhook",
            "display_phone_number": "+260000000000",
            "verified_name": "Test Business",
            "summary": {},
        },
    )

    workspace_token = base64.urlsafe_b64encode(
        workspace_id.encode()
    ).decode().rstrip("=")

    verify = client.get(
        (
            f"/api/v1/integrations/whatsapp/webhook/"
            f"{workspace_token}/{webhook_key}"
        ),
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": verify_token,
            "hub.challenge": "challenge-123",
        },
    )
    assert verify.status_code == 200
    assert verify.text == "challenge-123"

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "987654321",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "contacts": [
                                {
                                    "wa_id": "260971234567",
                                    "profile": {"name": "Teacher One"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "260971234567",
                                    "id": "wamid.TEST123",
                                    "timestamp": "1784800000",
                                    "type": "text",
                                    "text": {
                                        "body": "I paid but I need help getting started."
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(
        app_secret.encode(),
        raw,
        hashlib.sha256,
    ).hexdigest()

    response = client.post(
        (
            f"/api/v1/integrations/whatsapp/webhook/"
            f"{workspace_token}/{webhook_key}"
        ),
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200
    assert response.json()["messages_created"] == 1

    conversations = client.get(
        "/api/v1/integrations/whatsapp/conversations",
        headers=headers,
    )
    assert conversations.status_code == 200
    assert len(conversations.json()) == 1
    assert conversations.json()[0]["customer_name"] == "Teacher One"

    tickets = client.get("/api/v1/support/tickets", headers=headers)
    whatsapp_tickets = [
        item for item in tickets.json()
        if item.get("channel") == "whatsapp"
    ]
    assert len(whatsapp_tickets) == 1



def test_whatsapp_embedded_config_is_public_safe():
    response = client.get(
        "/api/v1/integrations/whatsapp/embedded/config",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["app_id"] == "1234567890"
    assert payload["config_id"] == "test-config-id"
    assert "app_secret" not in payload
    assert payload["webhook_callback_url"].endswith(
        "/api/v1/integrations/whatsapp/webhook"
    )


def test_global_whatsapp_webhook_routes_to_workspace():
    import hashlib
    import hmac
    import json

    from app.services.integration_utils import integration_store
    from app.services.secret_service import secret_service
    from app.services.whatsapp_integration_service import whatsapp_integration

    workspace_id = headers["X-Workspace-Id"]
    integration_store.save(
        workspace_id,
        "whatsapp",
        {
            "status": "connected",
            "connection_type": "embedded_signup_v4",
            "encrypted_access_token": secret_service.encrypt(
                "embedded-test-access-token-123456"
            ),
            "phone_number_id": "555000111",
            "waba_id": "555000999",
            "display_phone_number": "+260955500011",
            "verified_name": "Embedded Test Business",
            "summary": {},
        },
    )
    whatsapp_integration._save_route(workspace_id, "waba", "555000999")
    whatsapp_integration._save_route(workspace_id, "phone", "555000111")

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "555000999",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "555000111"},
                            "contacts": [
                                {
                                    "wa_id": "260977700011",
                                    "profile": {"name": "Embedded Customer"},
                                }
                            ],
                            "messages": [
                                {
                                    "from": "260977700011",
                                    "id": "wamid.EMBEDDED1",
                                    "timestamp": "1784800100",
                                    "type": "text",
                                    "text": {"body": "Can you help me renew?"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(
        b"test-meta-app-secret",
        raw,
        hashlib.sha256,
    ).hexdigest()

    verify = client.get(
        "/api/v1/integrations/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-platform-verify-token",
            "hub.challenge": "global-challenge",
        },
    )
    assert verify.status_code == 200
    assert verify.text == "global-challenge"

    response = client.post(
        "/api/v1/integrations/whatsapp/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200
    assert response.json()["messages_created"] == 1

    conversations = client.get(
        "/api/v1/integrations/whatsapp/conversations",
        headers=headers,
    ).json()
    assert any(
        item["customer_name"] == "Embedded Customer"
        for item in conversations
    )


def test_embedded_signup_completion_exchanges_code_and_saves_connection(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = str(payload)

        def json(self):
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, **kwargs):
            if url.endswith("/oauth/access_token"):
                return FakeResponse(200, {"access_token": "business-token-123456789"})
            if url.endswith("/777000111"):
                return FakeResponse(
                    200,
                    {
                        "display_phone_number": "+260977000111",
                        "verified_name": "Kondai Customer",
                        "quality_rating": "GREEN",
                        "platform_type": "CLOUD_API",
                        "account_mode": "LIVE",
                    },
                )
            return FakeResponse(404, {"error": {"message": "Not found"}})

        async def post(self, url, **kwargs):
            if url.endswith("/777000999/subscribed_apps"):
                return FakeResponse(200, {"success": True})
            if url.endswith("/777000111/register"):
                return FakeResponse(200, {"success": True})
            return FakeResponse(404, {"error": {"message": "Not found"}})

    monkeypatch.setattr(
        "app.services.whatsapp_integration_service.httpx.AsyncClient",
        FakeAsyncClient,
    )

    response = client.post(
        "/api/v1/integrations/whatsapp/embedded/complete",
        headers=headers,
        json={
            "code": "temporary-embedded-signup-code",
            "waba_id": "777000999",
            "phone_number_id": "777000111",
            "business_id": "777000555",
            "flow_type": "embedded_signup_v4",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is True
    assert payload["display_phone_number"] == "+260977000111"
    assert payload["onboarding_mode"] == "embedded_signup_v4"

    from app.core.repository import get_repository

    repository = get_repository()
    route = repository.get(
        "integration_routes",
        "whatsapp-phone-777000111",
        "__kondai_system__",
    )
    assert route is not None
    assert route["target_workspace_id"] == headers["X-Workspace-Id"]


def test_agentic_review_prepares_work_after_founder_continues():
    from app.services.integration_utils import integration_store
    from app.services.knowledge_graph_service import knowledge_graph

    agent_headers = {
        "X-User-Id": "agentic-founder",
        "X-Workspace-Id": "agentic-workspace",
    }
    workspace_id = agent_headers["X-Workspace-Id"]
    repository = get_repository()
    repository.clear_workspace(workspace_id)

    product = repository.create(
        "products",
        workspace_id,
        {
            "name": "Founder Product",
            "description": "A connected production product used for the operating review.",
            "github_repository": "founder/product",
        },
    )
    integration_store.save(
        workspace_id,
        "github",
        {
            "status": "repository_connected",
            "connection_type": "public_repository",
            "selected_repository": "founder/product",
            "selected_branch": "main",
            "last_synced_at": "2026-07-24T10:00:00+00:00",
            "product_id": product["id"],
        },
    )
    integration_store.save(
        workspace_id,
        "firestore",
        {
            "status": "connected",
            "project_id": "founder-product-project",
            "last_synced_at": "2026-07-24T10:02:00+00:00",
            "summary": {
                "total_customers": 120,
                "active_customers": 28,
                "paid_customers": 14,
                "total_accounts": 9,
                "active_accounts": 3,
            },
        },
    )
    knowledge_graph.ingest(
        workspace_id,
        "github",
        "GitHub repository: founder/product",
        {
            "repository": "founder/product",
            "file_count": 840,
            "languages": {"TypeScript": 500000, "Python": 310000},
            "recent_commits": 18,
            "open_bugs": 7,
            "manifests": {"package.json": "{}", "requirements.txt": ""},
            "recent_features": [
                "Add customer workspace onboarding",
                "Add approval-controlled campaign execution",
            ],
        },
        external_id="founder/product",
        product_id=product["id"],
    )
    knowledge_graph.ingest(
        workspace_id,
        "database",
        "Live product database — Firestore",
        {
            "provider": "firestore",
            "project_id": "founder-product-project",
            "total_customers": 120,
            "active_customers": 28,
            "paid_customers": 14,
            "total_accounts": 9,
            "active_accounts": 3,
            "subscription_records": 14,
            "event_records": 0,
            "document_records": 36,
        },
        external_id="firestore",
        product_id=product["id"],
    )

    review_response = client.post(
        "/api/v1/operations/initial-review",
        headers=agent_headers,
    )
    assert review_response.status_code == 200
    command = review_response.json()
    assert command["operation_run"]["status"] == "awaiting_founder"
    assert command["review"]["opening_message"].lower().startswith(
        "i have gone through"
    )
    assert len(command["findings"]) >= 2
    assert command["evidence"]
    assert command["recommendation"]["status"] == "awaiting_founder"

    recommendation_id = command["recommendation"]["id"]
    continue_response = client.post(
        f"/api/v1/operations/recommendations/{recommendation_id}/continue",
        headers=agent_headers,
        json={"founder_note": "Prepare a controlled first version."},
    )
    assert continue_response.status_code == 200
    continued = continue_response.json()
    assert continued["action_plan"]["status"] == "awaiting_final_approval"
    assert continued["action_plan"]["deliverables"]
    assert continued["approvals"]

    approval_id = continued["approvals"][0]["id"]
    assert client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers=agent_headers,
    ).status_code == 200
    executed = client.post(
        f"/api/v1/approvals/{approval_id}/execute",
        headers=agent_headers,
    )
    assert executed.status_code == 200
    assert executed.json()["execution_status"] == "executed"

    refreshed = client.post(
        f"/api/v1/operations/plans/{continued['action_plan']['id']}/outcome/refresh",
        headers=agent_headers,
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["outcome"]["status"] == "monitoring"
