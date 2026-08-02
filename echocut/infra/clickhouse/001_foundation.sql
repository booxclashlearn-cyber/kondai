CREATE DATABASE IF NOT EXISTS echocut;

CREATE TABLE IF NOT EXISTS echocut.system_events
(
  event_id UUID,
  project_id UUID,
  event_type LowCardinality(String),
  event_time DateTime64(3, 'UTC'),
  actor_id UUID,
  payload_json String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (project_id, event_time, event_id);

CREATE TABLE IF NOT EXISTS echocut.agent_tool_calls
(
  trace_id UUID,
  project_id Nullable(UUID),
  analysis_run_id Nullable(UUID),
  agent_name LowCardinality(String),
  tool_name LowCardinality(String),
  safe_arguments_json String,
  started_at DateTime64(3, 'UTC'),
  duration_ms UInt32,
  status LowCardinality(String),
  returned_row_count Nullable(UInt32),
  error_code Nullable(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(started_at)
ORDER BY (project_id, analysis_run_id, started_at, trace_id);

