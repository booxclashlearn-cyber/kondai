import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from .config import Settings


@dataclass(frozen=True)
class ToolCallAudit:
    trace_id: uuid.UUID
    project_id: uuid.UUID | None
    analysis_run_id: uuid.UUID | None
    agent_name: str
    tool_name: str
    safe_arguments_json: str
    started_at: datetime
    duration_ms: int
    status: str
    returned_row_count: int | None = None
    error_code: str | None = None

    def row(self) -> list:
        values = asdict(self)
        return [values[name] for name in values]


class ClickHouseGateway:
    def __init__(self, settings: Settings):
        self.settings = settings

    def client(self):
        import clickhouse_connect

        return clickhouse_connect.get_client(
            host=self.settings.clickhouse_host,
            port=self.settings.clickhouse_port,
            database=self.settings.clickhouse_database,
            username=self.settings.clickhouse_username,
            password=self.settings.clickhouse_password,
            secure=self.settings.clickhouse_secure,
            connect_timeout=2,
        )

    def health(self) -> tuple[str, str]:
        try:
            result = self.client().query("SELECT 1")
            return (
                ("ready", "Connected")
                if result.first_row[0] == 1
                else ("degraded", "Unexpected response")
            )
        except Exception:
            return "unavailable", "Connection failed"

    def record_system_event(
        self, project_id: uuid.UUID, event_type: str, actor_id: uuid.UUID, payload: dict
    ) -> None:
        self.client().insert(
            "system_events",
            [
                [
                    uuid.uuid4(),
                    project_id,
                    event_type,
                    datetime.now(UTC),
                    actor_id,
                    json.dumps(payload),
                ]
            ],
            column_names=[
                "event_id",
                "project_id",
                "event_type",
                "event_time",
                "actor_id",
                "payload_json",
            ],
        )

    def record_tool_call(self, audit: ToolCallAudit) -> None:
        self.client().insert("agent_tool_calls", [audit.row()], column_names=list(asdict(audit)))


def timed_audit(tool_name: str, arguments: dict) -> tuple[float, ToolCallAudit]:
    start = time.monotonic()
    audit = ToolCallAudit(
        uuid.uuid4(),
        None,
        None,
        "readiness",
        tool_name,
        json.dumps(arguments),
        datetime.now(UTC),
        0,
        "started",
    )
    return start, audit
