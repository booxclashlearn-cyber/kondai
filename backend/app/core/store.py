from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import get_settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonStore:
    COLLECTIONS = [
        "workspaces",
        "products",
        "positioning",
        "prospects",
        "campaigns",
        "messages",
        "approvals",
        "replies",
        "feedback",
        "briefings",
        "agent_runs",
        "events",
        "metrics",
    ]

    def __init__(self) -> None:
        self.path = Path(get_settings().store_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._ensure_file()

    def _empty(self) -> dict[str, Any]:
        return {collection: {} for collection in self.COLLECTIONS}

    def _ensure_file(self) -> None:
        if not self.path.exists():
            self.path.write_text(json.dumps(self._empty(), indent=2), encoding="utf-8")

    def _read(self) -> dict[str, Any]:
        with self.lock:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, FileNotFoundError):
                data = self._empty()
            for collection in self.COLLECTIONS:
                data.setdefault(collection, {})
            return data

    def _write(self, data: dict[str, Any]) -> None:
        with self.lock:
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp.replace(self.path)

    def list(self, collection: str, workspace_id: str) -> list[dict[str, Any]]:
        data = self._read()
        records = [
            deepcopy(record)
            for record in data[collection].values()
            if record.get("workspace_id") == workspace_id
        ]
        return sorted(records, key=lambda item: item.get("created_at", ""), reverse=True)

    def get(self, collection: str, record_id: str, workspace_id: str) -> dict[str, Any] | None:
        data = self._read()
        record = data[collection].get(record_id)
        if not record or record.get("workspace_id") != workspace_id:
            return None
        return deepcopy(record)

    def create(self, collection: str, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        record_id = payload.get("id") or str(uuid4())
        now = utc_now()
        record = {
            **payload,
            "id": record_id,
            "workspace_id": workspace_id,
            "created_at": payload.get("created_at", now),
            "updated_at": now,
        }
        data[collection][record_id] = record
        self._write(data)
        return deepcopy(record)

    def update(
        self,
        collection: str,
        record_id: str,
        workspace_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any] | None:
        data = self._read()
        record = data[collection].get(record_id)
        if not record or record.get("workspace_id") != workspace_id:
            return None
        record.update(changes)
        record["updated_at"] = utc_now()
        data[collection][record_id] = record
        self._write(data)
        return deepcopy(record)

    def count(self, collection: str, workspace_id: str) -> int:
        return len(self.list(collection, workspace_id))


store = JsonStore()
