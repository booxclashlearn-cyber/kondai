import uuid

from app.db import ExtractionDocumentRecord, MediaAssetRecord


def create_version(client, payload):
    project = client.post("/api/v1/projects", json=payload).json()
    version = client.post(
        f"/api/v1/projects/{project['id']}/versions", json={"label": "Cut A"}
    ).json()
    return project, version


def upload_inputs(client, version_id):
    script = client.post(
        f"/api/v1/versions/{version_id}/uploads/script",
        files={"file": ("screenplay.pdf", b"%PDF-1.7 synthetic", "application/pdf")},
    )
    video = client.post(
        f"/api/v1/versions/{version_id}/uploads/video",
        files={"file": ("rough-cut.mp4", b"synthetic video bytes", "video/mp4")},
        data={"duration_seconds": "240"},
    )
    return script, video


def test_upload_metadata_checksum_and_duplicate_guard(client, project_payload, session):
    _, version = create_version(client, project_payload)
    script, video = upload_inputs(client, version["id"])
    assert script.status_code == 201
    assert video.status_code == 201
    assert len(script.json()["checksum_sha256"]) == 64
    assert script.json()["original_name"] == "screenplay.pdf"
    assert session.query(MediaAssetRecord).count() == 2
    duplicate = client.post(
        f"/api/v1/versions/{version['id']}/uploads/script",
        files={"file": ("other.pdf", b"%PDF", "application/pdf")},
    )
    assert duplicate.status_code == 422


def test_upload_validation_rejects_type_duration_and_unsafe_name(client, project_payload):
    _, version = create_version(client, project_payload)
    bad_script = client.post(
        f"/api/v1/versions/{version['id']}/uploads/script",
        files={"file": ("attack.exe", b"payload", "application/octet-stream")},
    )
    bad_video = client.post(
        f"/api/v1/versions/{version['id']}/uploads/video",
        files={"file": ("film.mp4", b"video", "video/mp4")},
        data={"duration_seconds": "301"},
    )
    assert bad_script.status_code == 422
    assert bad_video.status_code == 422


def test_extraction_review_correction_approval_and_lock(client, project_payload, session):
    _, version = create_version(client, project_payload)
    upload_inputs(client, version["id"])
    response = client.post(f"/api/v1/versions/{version['id']}/extract")
    assert response.status_code == 201
    extraction = response.json()
    assert extraction["provider"] == "local_fixture"
    assert "no screenplay or video content was analysed" in extraction["content"]["limitations"][0]
    content = extraction["content"]
    content["characters"][0]["name"] = "Maya"
    content["scenes"][0]["heading"] = "INT. GUESTHOUSE - NIGHT"
    updated = client.patch(
        f"/api/v1/versions/{version['id']}/extraction", json={"content": content}
    )
    assert updated.status_code == 200
    assert updated.json()["content"]["characters"][0]["name"] == "Maya"
    approved = client.post(f"/api/v1/versions/{version['id']}/extraction/approve")
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"
    assert session.query(ExtractionDocumentRecord).one().reviewed_by is not None
    locked = client.patch(f"/api/v1/versions/{version['id']}/extraction", json={"content": content})
    assert locked.status_code == 409


def test_extraction_requires_both_inputs_and_enforces_ownership(client, project_payload, session):
    _, version = create_version(client, project_payload)
    assert client.post(f"/api/v1/versions/{version['id']}/extract").status_code == 409
    missing = client.get(f"/api/v1/versions/{uuid.uuid4()}/uploads")
    assert missing.status_code == 404
