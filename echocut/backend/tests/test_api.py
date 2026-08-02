import uuid

from sqlalchemy import select

from app.auth import DEV_USER_ID
from app.db import ActivityRecord, ProjectRecord, UserRecord


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_is_honest(client):
    data = client.get("/api/v1/system/readiness").json()["services"]
    assert data["api"]["status"] == "ready"
    assert data["postgresql"]["status"] == "ready"
    assert data["clickhouse_mcp"]["status"] == "not_configured"


def test_project_lifecycle_and_activity(client, project_payload):
    created = client.post("/api/v1/projects", json=project_payload)
    assert created.status_code == 201
    project = created.json()
    assert project["status"] == "draft"
    listed = client.get("/api/v1/projects").json()
    assert listed["total"] == 1
    updated = client.patch(f"/api/v1/projects/{project['id']}", json={"title": "Red Key Revised"})
    assert updated.json()["title"] == "Red Key Revised"
    activity = client.get(f"/api/v1/projects/{project['id']}/activity").json()["items"]
    assert {x["event_type"] for x in activity} == {"project.created", "project.updated"}


def test_project_validation(client, project_payload):
    project_payload["title"] = ""
    response = client.post("/api/v1/projects", json=project_payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_ownership_hides_foreign_project(client, session, project_payload):
    other = UserRecord(id=uuid.uuid4(), email="other@example.com", display_name="Other")
    session.add(other)
    session.flush()
    foreign = ProjectRecord(owner_id=other.id, **project_payload)
    session.add(foreign)
    session.commit()
    assert client.get(f"/api/v1/projects/{foreign.id}").status_code == 404


def test_versions_duplicate_and_invalid_label(client, project_payload):
    pid = client.post("/api/v1/projects", json=project_payload).json()["id"]
    assert (
        client.post(
            f"/api/v1/projects/{pid}/versions", json={"label": "Cut A", "description": "First"}
        ).status_code
        == 201
    )
    assert (
        client.post(f"/api/v1/projects/{pid}/versions", json={"label": "Cut A"}).status_code == 409
    )
    assert (
        client.post(f"/api/v1/projects/{pid}/versions", json={"label": "Director Cut"}).status_code
        == 422
    )
    events = client.get(f"/api/v1/projects/{pid}/activity").json()["items"]
    assert "film_version.created" in {x["event_type"] for x in events}


def test_repository_persists(client, session, project_payload):
    pid = client.post("/api/v1/projects", json=project_payload).json()["id"]
    assert (
        session.scalar(select(ProjectRecord).where(ProjectRecord.id == uuid.UUID(pid))) is not None
    )
    assert (
        session.scalar(select(ActivityRecord).where(ActivityRecord.project_id == uuid.UUID(pid)))
        is not None
    )
    assert session.get(UserRecord, DEV_USER_ID) is not None
