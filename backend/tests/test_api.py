import os
from pathlib import Path

os.environ["STORE_PATH"] = "data/test-store.json"
os.environ["AUTH_MODE"] = "dev"
os.environ["AI_MODE"] = "demo"
os.environ["EMAIL_MODE"] = "mock"

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

get_settings.cache_clear()

client = TestClient(app)
headers = {"X-User-Id": "test-user", "X-Workspace-Id": "test-workspace"}


def setup_module():
    path = Path("data/test-store.json")
    if path.exists():
        path.unlink()


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_vertical_slice():
    product_response = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "LaunchKit",
            "description": "A tool that helps developers prepare software launch assets.",
            "stage": "public_beta",
            "pricing": "$19 monthly",
            "launch_goal": "Find ten qualified testers",
            "target_customer_assumption": "Solo SaaS developers",
        },
    )
    assert product_response.status_code == 201
    product = product_response.json()

    analysis_response = client.post(
        f"/api/v1/products/{product['id']}/analyse",
        headers=headers,
    )
    assert analysis_response.status_code == 200
    positioning = analysis_response.json()

    approve_positioning = client.post(
        f"/api/v1/positioning/{positioning['id']}/approve",
        headers=headers,
    )
    assert approve_positioning.status_code == 200

    prospect_response = client.post(
        "/api/v1/prospects",
        headers=headers,
        json={
            "name": "Alex Founder",
            "email": "alex@example.com",
            "company": "Tiny SaaS",
            "role": "Founder",
            "source": "manual",
            "notes": "Recently launched a developer product.",
        },
    )
    assert prospect_response.status_code == 201
    prospect = prospect_response.json()

    qualification_response = client.post(
        f"/api/v1/prospects/{prospect['id']}/qualify",
        headers=headers,
        params={"product_id": product["id"]},
    )
    assert qualification_response.status_code == 200

    campaign_response = client.post(
        "/api/v1/campaigns",
        headers=headers,
        json={
            "name": "First founder interviews",
            "product_id": product["id"],
            "goal": "Recruit qualified early testers",
            "target_segment": "Solo SaaS founders",
        },
    )
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()

    prepare_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/prepare",
        headers=headers,
    )
    assert prepare_response.status_code == 200
    assert prepare_response.json()["created_approvals"] == 1

    approvals_response = client.get("/api/v1/approvals", headers=headers)
    approval = approvals_response.json()[0]

    assert client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        headers=headers,
    ).status_code == 200

    execute_response = client.post(
        f"/api/v1/approvals/{approval['id']}/execute",
        headers=headers,
    )
    assert execute_response.status_code == 200
    assert execute_response.json()["execution_status"] == "executed"

    briefing_response = client.post("/api/v1/briefings/generate", headers=headers)
    assert briefing_response.status_code == 200
