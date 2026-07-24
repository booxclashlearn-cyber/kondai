from __future__ import annotations
import json, threading
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4
from app.core.config import get_settings

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class Repository:
    def list(self, collection: str, workspace_id: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]: raise NotImplementedError
    def get(self, collection: str, record_id: str, workspace_id: str) -> dict[str, Any] | None: raise NotImplementedError
    def create(self, collection: str, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]: raise NotImplementedError
    def update(self, collection: str, record_id: str, workspace_id: str, changes: dict[str, Any]) -> dict[str, Any] | None: raise NotImplementedError
    def delete(self, collection: str, record_id: str, workspace_id: str) -> bool: raise NotImplementedError
    def clear_workspace(self, workspace_id: str) -> None: raise NotImplementedError

class JsonRepository(Repository):
    def __init__(self, path: str) -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True); self.lock = threading.RLock()
        if not self.path.exists(): self.path.write_text(json.dumps({"collections": {}}, indent=2), encoding="utf-8")
    def _read(self) -> dict[str, Any]:
        with self.lock:
            try: data = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError): data = {"collections": {}}
            data.setdefault("collections", {}); return data
    def _write(self, data: dict[str, Any]) -> None:
        with self.lock:
            temp = self.path.with_suffix(".tmp"); temp.write_text(json.dumps(data, indent=2), encoding="utf-8"); temp.replace(self.path)
    @staticmethod
    def _matches(record: dict[str, Any], filters: dict[str, Any] | None) -> bool:
        if not filters: return True
        return all(record.get(key) == value for key, value in filters.items())
    def list(self, collection: str, workspace_id: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        records = self._read()["collections"].get(collection, {})
        output = [deepcopy(r) for r in records.values() if r.get("workspace_id") == workspace_id and self._matches(r, filters)]
        return sorted(output, key=lambda item: item.get("created_at", ""), reverse=True)
    def get(self, collection: str, record_id: str, workspace_id: str) -> dict[str, Any] | None:
        record = self._read()["collections"].get(collection, {}).get(record_id)
        return deepcopy(record) if record and record.get("workspace_id") == workspace_id else None
    def create(self, collection: str, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._read(); records = data["collections"].setdefault(collection, {}); record_id = str(payload.get("id") or uuid4()); now = utc_now()
        record = {**payload, "id": record_id, "workspace_id": workspace_id, "created_at": payload.get("created_at", now), "updated_at": now}
        records[record_id] = record; self._write(data); return deepcopy(record)
    def update(self, collection: str, record_id: str, workspace_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        data = self._read(); records = data["collections"].setdefault(collection, {}); record = records.get(record_id)
        if not record or record.get("workspace_id") != workspace_id: return None
        record.update(changes); record["updated_at"] = utc_now(); records[record_id] = record; self._write(data); return deepcopy(record)
    def delete(self, collection: str, record_id: str, workspace_id: str) -> bool:
        data = self._read(); records = data["collections"].setdefault(collection, {}); record = records.get(record_id)
        if not record or record.get("workspace_id") != workspace_id: return False
        del records[record_id]; self._write(data); return True
    def clear_workspace(self, workspace_id: str) -> None:
        data = self._read()
        for collection, records in data["collections"].items(): data["collections"][collection] = {k:v for k,v in records.items() if v.get("workspace_id") != workspace_id}
        self._write(data)

class FirestoreRepository(Repository):
    def __init__(self) -> None: self._db: Any = None
    def _client(self) -> Any:
        if self._db is not None: return self._db
        import firebase_admin
        from firebase_admin import credentials, firestore
        settings = get_settings()
        try: app = firebase_admin.get_app("kondai")
        except ValueError:
            credential = credentials.Certificate(settings.firebase_service_account_path) if settings.firebase_service_account_path else credentials.ApplicationDefault()
            app = firebase_admin.initialize_app(credential, {"projectId": settings.firebase_project_id or None}, name="kondai")
        self._db = firestore.client(app=app); return self._db
    def _collection(self, collection: str, workspace_id: str) -> Any:
        return self._client().collection("workspaces").document(workspace_id).collection(collection)
    def list(self, collection: str, workspace_id: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        query = self._collection(collection, workspace_id)
        for key, value in (filters or {}).items(): query = query.where(key, "==", value)
        out=[]
        for doc in query.stream():
            payload=doc.to_dict() or {}; payload.setdefault("id",doc.id); payload.setdefault("workspace_id",workspace_id); out.append(payload)
        return sorted(out,key=lambda item:item.get("created_at",""),reverse=True)
    def get(self, collection: str, record_id: str, workspace_id: str) -> dict[str, Any] | None:
        doc=self._collection(collection,workspace_id).document(record_id).get()
        if not doc.exists:return None
        payload=doc.to_dict() or {}; payload.setdefault("id",doc.id); payload.setdefault("workspace_id",workspace_id); return payload
    def create(self, collection: str, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ref=self._collection(collection,workspace_id).document(str(payload.get("id") or uuid4())); now=utc_now(); record={**payload,"id":ref.id,"workspace_id":workspace_id,"created_at":payload.get("created_at",now),"updated_at":now}; ref.set(record); return record
    def update(self, collection: str, record_id: str, workspace_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        ref=self._collection(collection,workspace_id).document(record_id)
        if not ref.get().exists:return None
        ref.update({**changes,"updated_at":utc_now()}); return self.get(collection,record_id,workspace_id)
    def delete(self, collection: str, record_id: str, workspace_id: str) -> bool:
        ref=self._collection(collection,workspace_id).document(record_id)
        if not ref.get().exists:return False
        ref.delete(); return True
    def clear_workspace(self, workspace_id: str) -> None:
        workspace=self._client().collection("workspaces").document(workspace_id)
        for collection in workspace.collections():
            for document in collection.stream(): document.reference.delete()

@lru_cache
def get_repository() -> Repository:
    settings=get_settings()
    return FirestoreRepository() if settings.store_mode.lower()=="firestore" else JsonRepository(settings.json_store_path)
