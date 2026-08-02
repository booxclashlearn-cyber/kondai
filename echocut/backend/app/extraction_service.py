import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .db import (
    ExtractionDocumentRecord,
    ExtractionJobRecord,
    FilmVersionRecord,
    MediaAssetRecord,
    UserRecord,
)
from .extraction import GeminiExtractionAdapter, LocalExtractionAdapter
from .schemas import ExtractionContent
from .storage import configured_storage, validate_upload


class ExtractionService:
    def __init__(self, session: Session, settings: Settings):
        self.session, self.settings = session, settings

    def assets(self, version_id: uuid.UUID) -> list[MediaAssetRecord]:
        return list(
            self.session.scalars(
                select(MediaAssetRecord)
                .where(MediaAssetRecord.version_id == version_id)
                .order_by(MediaAssetRecord.created_at)
            )
        )

    def save_asset(
        self,
        version: FilmVersionRecord,
        kind: str,
        name: str,
        content_type: str,
        data: bytes,
        duration_seconds: int | None,
    ) -> MediaAssetRecord:
        if self.session.scalar(
            select(MediaAssetRecord).where(
                MediaAssetRecord.version_id == version.id, MediaAssetRecord.kind == kind
            )
        ):
            raise ValueError(f"A {kind} is already uploaded for this version")
        if kind == "script" and (content_type != "application/pdf" or len(data) > 25 * 1024 * 1024):
            raise ValueError("Screenplay must be a PDF no larger than 25 MiB")
        if kind == "video" and (
            content_type not in {"video/mp4", "video/quicktime"}
            or duration_seconds is None
            or not 1 <= duration_seconds <= 300
        ):
            raise ValueError("Rough cut must be MP4/MOV with a duration between 1 and 300 seconds")
        filename = validate_upload(name, content_type, len(data))
        storage_name = f"{version.id}-{kind}-{uuid.uuid4()}-{filename}"
        stored = configured_storage(self.settings.local_storage_path, self.settings.gcs_bucket).put(
            storage_name, data, content_type
        )
        asset = MediaAssetRecord(
            version_id=version.id,
            kind=kind,
            original_name=filename,
            content_type=content_type,
            size_bytes=len(data),
            checksum_sha256=hashlib.sha256(data).hexdigest(),
            storage_uri=stored.uri,
            duration_seconds=duration_seconds,
        )
        self.session.add(asset)
        if kind == "script":
            version.script_status = "uploaded"
        else:
            version.video_status = "uploaded"
        self.session.commit()
        return asset

    def start(self, version: FilmVersionRecord) -> ExtractionDocumentRecord:
        assets = {asset.kind: asset for asset in self.assets(version.id)}
        if "script" not in assets or "video" not in assets:
            raise ValueError("Upload both a screenplay and rough cut before extraction")
        previous = self.latest(version.id)
        if previous and previous.review_status == "approved":
            raise ValueError("Approved extraction cannot be replaced")
        adapter = (
            LocalExtractionAdapter()
            if self.settings.extraction_mode == "local"
            else GeminiExtractionAdapter(
                self.settings.google_cloud_project or "",
                self.settings.google_cloud_region,
                self.settings.gemini_model,
            )
        )
        job = ExtractionJobRecord(
            version_id=version.id,
            status="processing",
            provider=adapter.provider,
            model_name=adapter.model_name,
        )
        self.session.add(job)
        self.session.flush()
        try:
            content = adapter.extract(assets["script"], assets["video"])
            job.status = "completed"
            document = ExtractionDocumentRecord(
                job_id=job.id, version_id=version.id, content=content.model_dump(mode="json")
            )
            self.session.add(document)
            version.script_status = version.video_status = "ready"
            self.session.commit()
            return document
        except Exception:
            job.status, job.error_code = "failed", "provider_unavailable"
            self.session.commit()
            raise

    def latest(self, version_id: uuid.UUID) -> ExtractionDocumentRecord | None:
        return self.session.scalar(
            select(ExtractionDocumentRecord)
            .where(ExtractionDocumentRecord.version_id == version_id)
            .order_by(ExtractionDocumentRecord.created_at.desc())
        )

    def validate_content(self, content: ExtractionContent) -> None:
        scene_ids = {scene.id for scene in content.scenes}
        character_ids = {character.id for character in content.characters}
        if len(scene_ids) != len(content.scenes) or len(character_ids) != len(content.characters):
            raise ValueError("Scene and character IDs must be unique")
        for scene in content.scenes:
            if scene.end_ms <= scene.start_ms or any(
                value not in character_ids for value in scene.character_ids
            ):
                raise ValueError("Scene ranges and character references must be valid")
        for fact in content.story_facts:
            if fact.introduced_scene_id not in scene_ids or (
                fact.payoff_scene_id and fact.payoff_scene_id not in scene_ids
            ):
                raise ValueError("Story facts must reference existing scenes")

    def update(
        self, document: ExtractionDocumentRecord, content: ExtractionContent
    ) -> ExtractionDocumentRecord:
        if document.review_status == "approved":
            raise ValueError("Approved extraction is immutable")
        self.validate_content(content)
        document.content = content.model_dump(mode="json")
        self.session.commit()
        return document

    def approve(
        self, document: ExtractionDocumentRecord, user: UserRecord
    ) -> ExtractionDocumentRecord:
        content = ExtractionContent.model_validate(document.content)
        self.validate_content(content)
        document.review_status = "approved"
        document.reviewed_by = user.id
        document.reviewed_at = datetime.now(UTC)
        self.session.commit()
        return document
