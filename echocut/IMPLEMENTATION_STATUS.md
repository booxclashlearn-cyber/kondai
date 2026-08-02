# Implementation status

**Date:** 1 August 2026

**Phase:** Phase 2 — Extraction review increment
**Result:** Partially complete

## Implemented

- All Phase 1 foundation capabilities remain intact.
- Project-owned screenplay PDF and MP4/MOV rough-cut multipart upload endpoints.
- Central validation: screenplay 25 MiB cap, media 500 MiB cap, rough-cut 1–300 second duration, MIME allowlist and secure filenames.
- SHA-256 checksums, private storage URIs and upload activity events.
- Local/GCS storage selection through the existing storage abstraction.
- Alembic `0002` migration for media assets, extraction jobs and extraction documents.
- Typed extraction schema for scenes, characters, facts/reveals/props/relationships, timestamped evidence and limitations.
- Persisted provider/model/prompt/status provenance.
- Deterministic local extraction adapter clearly labelled `local_fixture`; it does not inspect or claim to inspect media.
- Gemini adapter/transport boundary with typed response validation and fake transport contract test.
- Editable extraction-review screen and immutable human approval gate.
- Dashboard links for each film version; Phase 3 audience analysis remains disabled.
- Ownership, invalid media, missing prerequisites, duplicate media, corrections, approval and post-approval lock tests.

## Verification results

- Backend tests: **18 passed**.
- Backend lint/format: **passed**.
- Frontend tests: **8 passed**.
- Frontend lint: **passed**.
- Frontend strict type check: **passed**.
- Frontend production build: **passed**; 1,815 modules transformed, JS 390.57 kB (121.35 kB gzip), CSS 11.33 kB (3.22 kB gzip).
- Alembic upgrades `0001 -> 0002`, seed and Phase 2 table inspection: **passed against temporary SQLite**.

## Still incomplete for Phase 2

- Live Gemini/Vertex AI document and video execution worker.
- Background queue/checkpoint processing and progress polling; local extraction currently completes in the request.
- Production GCS signed/resumable upload sessions and media deletion/retention controls.
- Automated video-duration probing rather than client-supplied duration confirmed by server metadata.
- Rich creation/removal/reordering controls for every extraction entity; current UI edits the generated structured fields.
- PostgreSQL/GCS/Docker integration verification on a Docker-capable host.

Docker is not installed in this environment, so PostgreSQL, ClickHouse and container builds remain unverified. No external model result is simulated or claimed.

## Credentials still required

- Google Cloud project credentials and GCS bucket for cloud media storage.
- Vertex AI credentials/runtime transport for live Gemini extraction.
- Firebase credentials only for Firebase authentication.
- Official ClickHouse MCP read-only credentials for live MCP.

## Recommended next Phase 2 increment

Implement server-verified media probing and GCS resumable uploads, then connect a background Vertex Gemini worker that reads private GCS URIs, returns the existing `ExtractionContent` schema, persists retry/checkpoint state and exposes progress polling. Add golden-film and adversarial prompt-injection fixtures before marking extraction complete.

## Exact next development prompt summary

“Finish EchoCut Phase 2 with GCS resumable uploads, ffprobe-based duration validation, background extraction jobs, a real Vertex Gemini transport producing the existing typed schema, polling/progress UI, retry checkpoints, golden-film fixtures, prompt-injection tests and PostgreSQL/GCS integration verification; do not begin persona simulation.”
