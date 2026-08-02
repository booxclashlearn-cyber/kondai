import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ShortText = Annotated[str, Field(min_length=1, max_length=160)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str
    created_at: datetime
    local_only: bool = False


class ProjectCreate(BaseModel):
    title: ShortText
    genre: Annotated[str, Field(min_length=2, max_length=80)]
    intended_audience: Annotated[str, Field(min_length=2, max_length=240)]
    target_duration_seconds: Annotated[int, Field(ge=30, le=21600)]
    description: Annotated[str, Field(max_length=2000)] = ""


class ProjectUpdate(BaseModel):
    title: Annotated[str | None, Field(min_length=1, max_length=160)] = None
    genre: Annotated[str | None, Field(min_length=2, max_length=80)] = None
    intended_audience: Annotated[str | None, Field(min_length=2, max_length=240)] = None
    target_duration_seconds: Annotated[int | None, Field(ge=30, le=21600)] = None
    description: Annotated[str | None, Field(max_length=2000)] = None


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    label: Literal["Cut A", "Cut B"]
    version_number: int
    description: str
    script_status: str
    video_status: str
    created_at: datetime
    updated_at: datetime


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    genre: str
    intended_audience: str
    target_duration_seconds: int
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    versions: list[VersionOut] = []


class VersionCreate(BaseModel):
    label: Literal["Cut A", "Cut B"]
    description: Annotated[str, Field(max_length=1000)] = ""


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    actor_id: uuid.UUID
    event_type: str
    message: str
    metadata: dict
    created_at: datetime


class Page(BaseModel):
    items: list
    page: int
    page_size: int
    total: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class MediaAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version_id: uuid.UUID
    kind: Literal["script", "video"]
    original_name: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    duration_seconds: int | None
    created_at: datetime


class Character(BaseModel):
    id: str = Field(pattern=r"^CHAR-[0-9]{3}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)


class StoryFact(BaseModel):
    id: str = Field(pattern=r"^FACT-[0-9]{3}$")
    statement: str = Field(min_length=1, max_length=500)
    fact_type: Literal["fact", "reveal", "prop", "relationship"]
    introduced_scene_id: str
    payoff_scene_id: str | None = None


class EvidenceCue(BaseModel):
    id: str = Field(pattern=r"^EV-[0-9]{3}$")
    timestamp_ms: int = Field(ge=0, le=300000)
    event_type: Literal["dialogue", "visual", "audio", "object"]
    summary: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class Scene(BaseModel):
    id: str = Field(pattern=r"^SC-[0-9]{3}$")
    scene_number: int = Field(ge=1, le=200)
    heading: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1000)
    start_ms: int = Field(ge=0, le=300000)
    end_ms: int = Field(gt=0, le=300000)
    character_ids: list[str] = Field(default_factory=list, max_length=30)


class ExtractionContent(BaseModel):
    scenes: list[Scene] = Field(min_length=1, max_length=200)
    characters: list[Character] = Field(default_factory=list, max_length=100)
    story_facts: list[StoryFact] = Field(default_factory=list, max_length=500)
    evidence: list[EvidenceCue] = Field(default_factory=list, max_length=2000)
    limitations: list[str] = Field(default_factory=list, max_length=20)


class ExtractionOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    version_id: uuid.UUID
    job_status: str
    provider: str
    model_name: str | None
    review_status: str
    content: ExtractionContent
    created_at: datetime
    updated_at: datetime


class ExtractionUpdate(BaseModel):
    content: ExtractionContent
