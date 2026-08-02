# EchoCut — The AI Test Audience

EchoCut is an evidence-first film-editing intelligence platform. The current build includes the Phase 1 foundation plus a Phase 2 extraction-review vertical slice: project-scoped screenplay and rough-cut uploads, checksummed media metadata, persisted extraction jobs, editable typed story graphs and a human approval gate.

Local extraction produces an explicitly labelled deterministic review fixture so the workflow remains usable without credentials. It is never represented as Gemini or media analysis. Audience simulation and diagnostic findings are not implemented yet.

## Architecture summary

- React 19, Vite, strict TypeScript, Tailwind, React Router, TanStack Query, React Hook Form and Zod.
- FastAPI, Pydantic, SQLAlchemy and Alembic with repository-owned operational metadata.
- PostgreSQL for the Phase 1 local metadata path; the repository boundary permits a later Firestore adapter.
- ClickHouse MergeTree event/audit tables with trusted backend ingestion separated from read-only agent MCP access.
- Development auth for local work and a validated Firebase adapter boundary.
- Local media storage and a typed Google Cloud Storage implementation (upload UI is Phase 2).
- PDF and MP4/MOV uploads with type, size, duration, checksum and ownership validation.
- Typed scenes, characters, story facts/reveals/props, evidence cues and immutable approval records.
- Gemini extraction adapter contract with a fake transport test; live Vertex worker remains configuration work.

## Prerequisites

- Docker Desktop with Compose (recommended)
- Python 3.13 and Node.js 22+ for host development
- PowerShell 7 or Make (optional convenience wrapper)

## Environment setup

```powershell
cd echocut
Copy-Item .env.example .env
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 setup
```

The development identity is local-only and created from `DEVELOPMENT_USER_EMAIL`/`DEVELOPMENT_USER_NAME` defaults. Production refuses development authentication unless `ALLOW_DEVELOPMENT_AUTH=true` is explicitly set.

## Docker setup

```powershell
docker compose up --build
```

Open `http://localhost:5173`; API docs are at `http://localhost:8000/docs`. Backend startup applies migrations and seeds **The Red Key** with Cut A. Data persists in named volumes.

```powershell
docker compose down
# Add -v only when you intentionally want to delete local database data.
```

## Non-Docker development

Start only data services:

```powershell
docker compose up -d postgres clickhouse
```

Terminal 1:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Terminal 2:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Vite proxies `/api` and `/health` to port 8000. Set `VITE_API_URL` only when the API is on another origin.

## Extraction review

Create a cut from the project dashboard and open **Extraction review**. Upload one screenplay PDF (maximum 25 MiB) and one MP4/MOV rough cut (maximum five minutes), create the draft, correct its structured fields and approve it. Approved documents are immutable. `EXTRACTION_MODE=local` is the credential-free default and is visibly labelled `local_fixture`; `EXTRACTION_MODE=gemini` requires `GOOGLE_CLOUD_PROJECT` and the Vertex runtime transport.

## Commands

| Purpose | PowerShell | Make |
|---|---|---|
| Setup | `scripts/dev.ps1 setup` | `make setup` |
| Full Docker dev | `scripts/dev.ps1 dev` | `make dev` |
| Tests | `scripts/dev.ps1 test` | `make test` |
| Lint | `scripts/dev.ps1 lint` | `make lint` |
| Type check | `scripts/dev.ps1 typecheck` | `make typecheck` |
| Migration | `scripts/dev.ps1 migrate` | `make migrate` |
| Seed | `scripts/dev.ps1 seed` | `make seed` |
| Build | `scripts/dev.ps1 build` | `make build` |
| Stop | `scripts/dev.ps1 down` | `make down` |

Direct verification:

```powershell
cd backend
pytest -q
ruff check .
cd ../frontend
npm.cmd test
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

## ClickHouse MCP

Trusted API writes use `ClickHouseGateway`; agent reads use the MCP client abstraction and never accept arbitrary SQL from the frontend. The default state is honestly reported as `not_configured`.

1. Install `uv` and the official `mcp-clickhouse` package.
2. Create a ClickHouse user with read-only access to the required `echocut` analytical tables.
3. Follow [infra/mcp/clickhouse-mcp.example.json](infra/mcp/clickhouse-mcp.example.json) for environment values.
4. Set `CLICKHOUSE_MCP_COMMAND=uv` and set `CLICKHOUSE_MCP_ARGS` to the official server launch arguments for the installed release.
5. Expose the bounded `echocut_clickhouse_health` proof tool (a `SELECT 1`/server-version equivalent) in the server configuration before enabling readiness.

The stdio adapter speaks MCP JSON-RPC `tools/call`, has a timeout, sanitises errors, and is contract-tested with a fake transport. Live MCP remains unavailable until the official server is installed and configured; REST/SQL calls are never described as MCP calls.

## Current limitations

- The upload workflow currently sends multipart files through the API; production GCS signed/resumable sessions remain to be added.
- The live Vertex Gemini transport worker is not enabled; the typed adapter and fake contract are implemented.
- Firebase and GCS require external configuration; local development does not.
- Live ClickHouse/MCP verification requires Docker and the official MCP server.
- Sample timeline values are deterministic UI fixtures, visibly labelled as preview data.

## Troubleshooting

- `PostgreSQL unavailable`: run `docker compose up -d postgres`, then `python -m alembic upgrade head`.
- `ClickHouse unavailable`: inspect `docker compose logs clickhouse`; the HTTP port is 8123.
- `MCP not_configured`: expected until the command and official server environment are supplied.
- PowerShell blocks `npm.ps1`: use `npm.cmd` as the scripts do.
- Vite config traversal errors in restricted Windows environments: the scripts use Vite's `--configLoader runner` mode.

## Repository structure

```text
echocut/
├── frontend/       React application and tests
├── backend/        FastAPI application, Alembic and tests
├── infra/          ClickHouse bootstrap and MCP template
├── docs/           Product documentation location
├── scripts/        Cross-platform PowerShell task runner
├── ARCHITECTURE.md
└── IMPLEMENTATION_STATUS.md
```

Licensed under Apache-2.0.
