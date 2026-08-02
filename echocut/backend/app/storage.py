import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

ALLOWED_MEDIA_TYPES = {"application/pdf", "video/mp4", "video/quicktime"}
MAX_FILE_SIZE = 500 * 1024 * 1024


@dataclass(frozen=True)
class FileMetadata:
    name: str
    content_type: str
    size: int
    uri: str


def safe_filename(value: str) -> str:
    name = Path(value).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    if not cleaned:
        raise ValueError("Filename is invalid")
    return cleaned[:180]


def validate_upload(name: str, content_type: str, size: int) -> str:
    if content_type not in ALLOWED_MEDIA_TYPES:
        raise ValueError("Unsupported file type")
    if size <= 0 or size > MAX_FILE_SIZE:
        raise ValueError("File size is outside the allowed range")
    return safe_filename(name)


class MediaStorage(ABC):
    @abstractmethod
    def put(self, name: str, data: bytes, content_type: str) -> FileMetadata: ...


class LocalMediaStorage(MediaStorage):
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def put(self, name: str, data: bytes, content_type: str) -> FileMetadata:
        filename = validate_upload(name, content_type, len(data))
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / filename
        target.write_bytes(data)
        return FileMetadata(filename, content_type, len(data), target.as_uri())


class GCSMediaStorage(MediaStorage):
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name

    def put(self, name: str, data: bytes, content_type: str) -> FileMetadata:
        from google.cloud import storage

        filename = validate_upload(name, content_type, len(data))
        blob = storage.Client().bucket(self.bucket_name).blob(filename)
        blob.upload_from_string(data, content_type=content_type)
        return FileMetadata(
            filename, content_type, len(data), f"gs://{self.bucket_name}/{filename}"
        )


def configured_storage(local_path: str, gcs_bucket: str | None) -> MediaStorage:
    return GCSMediaStorage(gcs_bucket) if gcs_bucket else LocalMediaStorage(local_path)
