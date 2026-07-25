import os

# Configure services before importing app.main; several integrations read
# settings at module import time.
os.environ.setdefault("AUTH_MODE", "dev")
os.environ.setdefault("AI_MODE", "demo")
os.environ.setdefault("STORE_MODE", "json")
os.environ.setdefault("JSON_STORE_PATH", "data/test-store.json")
os.environ.setdefault(
    "INTEGRATION_ENCRYPTION_KEY",
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
)
os.environ.setdefault("META_APP_ID", "1234567890")
os.environ.setdefault("META_APP_SECRET", "test-meta-app-secret")
os.environ.setdefault("META_EMBEDDED_SIGNUP_CONFIG_ID", "test-config-id")
os.environ.setdefault("META_WEBHOOK_VERIFY_TOKEN", "test-platform-verify-token")
os.environ.setdefault("PUBLIC_API_BASE_URL", "https://api.example.com")

from fastapi.testclient import TestClient

from app.main import app


LOCAL_ORIGIN = "http://localhost:5173"
LOCAL_IP_ORIGIN = "http://127.0.0.1:5173"
PRODUCTION_ORIGIN = "https://kondai-flax.vercel.app"


def _preflight(origin: str):
    with TestClient(app) as client:
        return client.options(
            "/api/v1/onboarding/status",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": (
                    "x-user-id,x-workspace-id,content-type"
                ),
            },
        )


def test_localhost_preflight_is_allowed() -> None:
    response = _preflight(LOCAL_ORIGIN)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN


def test_loopback_ip_preflight_is_allowed() -> None:
    response = _preflight(LOCAL_IP_ORIGIN)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == LOCAL_IP_ORIGIN


def test_vercel_preflight_is_allowed() -> None:
    response = _preflight(PRODUCTION_ORIGIN)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PRODUCTION_ORIGIN


def test_local_onboarding_get_has_cors_header() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/onboarding/status",
            headers={
                "Origin": LOCAL_ORIGIN,
                "X-User-Id": "local-founder",
                "X-Workspace-Id": "local-workspace",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN


def test_production_onboarding_get_has_cors_header() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/onboarding/status",
            headers={
                "Origin": PRODUCTION_ORIGIN,
                "X-User-Id": "booxclash-founder",
                "X-Workspace-Id": "booxclash-workspace",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PRODUCTION_ORIGIN


def test_error_response_still_has_cors_header() -> None:
    # An unknown API path proves that non-success responses retain CORS.
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/v1/route-that-does-not-exist",
            headers={"Origin": LOCAL_ORIGIN},
        )

    assert response.status_code == 404
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN


def test_cors_diagnostic_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/cors-status",
            headers={"Origin": LOCAL_ORIGIN},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    payload = response.json()
    assert LOCAL_ORIGIN in payload["allowed_origins"]
    assert PRODUCTION_ORIGIN in payload["allowed_origins"]
