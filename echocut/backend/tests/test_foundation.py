import asyncio
import json
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.clickhouse import ToolCallAudit
from app.config import Settings
from app.db import MediaAssetRecord
from app.extraction import GeminiExtractionAdapter
from app.mcp import DisabledMCPClient, StdioMCPClient
from app.storage import safe_filename, validate_upload


def test_production_development_auth_guard():
    with pytest.raises(ValidationError):
        Settings(app_env="production", auth_mode="development", allow_development_auth=False)


def test_firebase_configuration_validation():
    with pytest.raises(ValidationError):
        Settings(auth_mode="firebase", firebase_project_id=None)


def test_disabled_mcp_state():
    assert asyncio.run(DisabledMCPClient().readiness())[0] == "not_configured"


class FakeTransport:
    async def request(self, method, params, timeout):
        assert method == "tools/call"
        assert params == {"name": "echocut_clickhouse_health", "arguments": {}}
        assert timeout == 2
        return {"content": [{"type": "text", "text": "1"}], "isError": False}


def test_mcp_health_contract():
    result = asyncio.run(StdioMCPClient(FakeTransport(), 2).clickhouse_health())
    assert result.content[0]["text"] == "1" and not result.is_error


def test_clickhouse_audit_serialization_excludes_raw_content():
    audit = ToolCallAudit(
        uuid.uuid4(),
        None,
        None,
        "analytics",
        "echocut_clickhouse_health",
        json.dumps({"bounded": True}),
        datetime.now(UTC),
        12,
        "success",
        1,
        None,
    )
    row = audit.row()
    assert len(row) == 11
    assert "screenplay" not in json.dumps(row, default=str)


def test_secure_upload_validation():
    assert safe_filename("../../rough cut.mp4") == "rough_cut.mp4"
    assert validate_upload("film.mp4", "video/mp4", 1024) == "film.mp4"
    with pytest.raises(ValueError):
        validate_upload("film.exe", "application/octet-stream", 1024)


class FakeGeminiTransport:
    def extract(self, **kwargs):
        assert kwargs["model_name"] == "gemini-test"
        assert kwargs["prompt_version"] == "extraction-v1"
        return {
            "scenes": [
                {
                    "id": "SC-001",
                    "scene_number": 1,
                    "heading": "OPEN",
                    "summary": "A scene",
                    "start_ms": 0,
                    "end_ms": 1000,
                    "character_ids": [],
                }
            ],
            "characters": [],
            "story_facts": [],
            "evidence": [],
            "limitations": [],
        }


def test_gemini_adapter_contract_with_fake_transport():
    script = MediaAssetRecord(storage_uri="gs://bucket/script.pdf", original_name="script.pdf")
    video = MediaAssetRecord(storage_uri="gs://bucket/video.mp4", original_name="video.mp4")
    adapter = GeminiExtractionAdapter("project", "region", "gemini-test", FakeGeminiTransport())
    assert adapter.extract(script, video).scenes[0].heading == "OPEN"
