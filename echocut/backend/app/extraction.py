import uuid
from abc import ABC, abstractmethod
from typing import Protocol

from .db import MediaAssetRecord
from .schemas import Character, EvidenceCue, ExtractionContent, Scene, StoryFact


class ExtractionAdapter(ABC):
    provider: str
    model_name: str | None

    @abstractmethod
    def extract(self, script: MediaAssetRecord, video: MediaAssetRecord) -> ExtractionContent: ...


class LocalExtractionAdapter(ExtractionAdapter):
    """Deterministic development adapter; output is always labelled local fixture data."""

    provider = "local_fixture"
    model_name = None

    def extract(self, script: MediaAssetRecord, video: MediaAssetRecord) -> ExtractionContent:
        duration_ms = min((video.duration_seconds or 240) * 1000, 300000)
        midpoint = duration_ms // 2
        return ExtractionContent(
            scenes=[
                Scene(
                    id="SC-001",
                    scene_number=1,
                    heading="OPENING",
                    summary="Opening story setup pending human correction.",
                    start_ms=0,
                    end_ms=midpoint,
                    character_ids=["CHAR-001"],
                ),
                Scene(
                    id="SC-002",
                    scene_number=2,
                    heading="PAYOFF",
                    summary="Closing story beat pending human correction.",
                    start_ms=midpoint,
                    end_ms=duration_ms,
                    character_ids=["CHAR-001"],
                ),
            ],
            characters=[
                Character(
                    id="CHAR-001",
                    name="Unknown lead",
                    description="Rename during extraction review.",
                )
            ],
            story_facts=[
                StoryFact(
                    id="FACT-001",
                    statement="A key story fact requires confirmation.",
                    fact_type="fact",
                    introduced_scene_id="SC-001",
                    payoff_scene_id="SC-002",
                )
            ],
            evidence=[
                EvidenceCue(
                    id="EV-001",
                    timestamp_ms=0,
                    event_type="visual",
                    summary="Placeholder cue requires human verification.",
                    confidence=0,
                )
            ],
            limitations=[
                "Deterministic local fixture; no screenplay or video content was analysed.",
                f"Inputs recorded as {script.original_name} and {video.original_name}.",
            ],
        )


class GeminiTransport(Protocol):
    def extract(
        self, *, script_uri: str, video_uri: str, model_name: str, prompt_version: str
    ) -> dict: ...


class GeminiExtractionAdapter(ExtractionAdapter):
    provider = "gemini_vertex_ai"

    def __init__(
        self,
        project_id: str,
        region: str,
        model_name: str,
        transport: GeminiTransport | None = None,
    ):
        self.project_id, self.region, self.model_name = project_id, region, model_name
        self.transport = transport

    def extract(self, script: MediaAssetRecord, video: MediaAssetRecord) -> ExtractionContent:
        if not self.transport:
            raise RuntimeError(
                "Gemini extraction requires the Phase 2 Vertex AI runtime worker configuration"
            )
        payload = self.transport.extract(
            script_uri=script.storage_uri,
            video_uri=video.storage_uri,
            model_name=self.model_name,
            prompt_version="extraction-v1",
        )
        return ExtractionContent.model_validate(payload)


def next_asset_name(version_id: uuid.UUID, kind: str, original: str) -> str:
    return f"{version_id}/{kind}-{uuid.uuid4()}-{original}"
