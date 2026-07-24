# Kondai — Founder Operations Platform

**Your first operating team, before your first hire.**

Kondai connects to the sources of truth around a software product, reviews the
business automatically and turns verified evidence into controlled action.

The customer experiences one coordinated Kondai operating partner. Internal
specialist services remain separated in the backend for safety, permissions and
quality control, but their architecture names are not exposed in the normal user
interface.

## What this build does

- Requires a real GitHub codebase before opening the workspace.
- Connects a live Cloud Firestore product database.
- Starts an operating review when GitHub and the Product Database are connected.
- Shows: “I have gone through the connected sources. Here is what I found.”
- Produces ranked findings with source-linked evidence.
- States missing evidence when Stripe, analytics or customer channels are absent.
- Recommends exactly one best next action.
- Asks the founder for permission before preparing work.
- Lets the founder inspect evidence, change the direction or put it on hold.
- Prepares campaign content, customer responses or internal tasks after permission.
- Requires final approval before execution.
- Creates an outcome-monitoring record after execution.
- Supports live Stripe, PostHog, Gmail and WhatsApp integrations.
- Stores operational state in JSON locally or Firestore in production.
- Uses Vertex AI Gemini 2.5 Flash when configured.
- Uses an evidence-based deterministic fallback when Vertex AI is unavailable.

See `docs/agentic-activation.md` for the complete operating cycle.

## Quick start

### Backend

```powershell
cd backend
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

API documentation:

```text
http://localhost:8000/docs
```

### Frontend

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Application:

```text
http://localhost:5173
```

## First operating review

1. Connect GitHub and select the product repository.
2. Open **Connections** and connect the Product Database.
3. Map the relevant Firestore collections.
4. After the database read completes, open **Overview**.
5. Kondai displays the review scope, findings, evidence and recommended next action.
6. Select **Continue** to let Kondai prepare the work.
7. Review the final deliverable and approve it before execution.
8. Refresh the outcome report as new data arrives.

## Vertex AI

The project runs in deterministic evidence mode until Vertex AI is configured:

```env
AI_MODE=vertex
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
GEMINI_MODEL=gemini-2.5-flash
```

Authenticate locally:

```powershell
gcloud auth application-default login
```

Without Vertex AI, Kondai still produces an honest review from the connected source
metrics. It does not invent missing data.

## Credential encryption

Generate the integration encryption key once:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save it in `backend/.env`:

```env
INTEGRATION_ENCRYPTION_KEY=your-generated-key
```

Do not change the key after connecting services and do not commit `.env`.

## Storage

Local development:

```env
STORE_MODE=json
JSON_STORE_PATH=data/store.json
```

Production Firestore operational store:

```env
STORE_MODE=firestore
FIREBASE_PROJECT_ID=your-kondai-project-id
```

The Product Database connector is separate: it reads a founder's external Firestore
project using an encrypted, least-privilege service account.

## Live integrations

- GitHub: repository metadata, README, file tree, languages, commits and issues.
- Cloud Firestore: customer, account, subscription, event and document snapshots.
- Stripe: subscriptions, MRR, ARR, revenue, churn and revenue risk.
- PostHog: active users, events, activation and feature usage.
- Gmail: customer messages imported as support issues.
- WhatsApp: Embedded Signup and signed inbound-message webhooks.

Detailed setup is available in:

```text
docs/github-onboarding.md
docs/live-integrations.md
docs/whatsapp-integration.md
docs/whatsapp-embedded-signup.md
```

## Validation

Backend tests cover the complete cycle:

```text
connect evidence
→ run operating review
→ inspect findings
→ continue recommendation
→ prepare deliverable
→ final approval
→ execute
→ refresh outcome
```

Run:

```powershell
cd backend
pytest -q
```

Frontend validation:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Production work still required

- Replace local development headers with the full Firebase Authentication UI.
- Move integration credentials from repository storage to Google Secret Manager.
- Replace local workflow execution with Cloud Tasks and retry/dead-letter policies.
- Add real outbound email and social-provider adapters.
- Add scheduled daily reviews and outcome refreshes through Cloud Scheduler.
- Add BigQuery and vector retrieval for larger datasets and deeper cohort analysis.
- Complete Meta verification and App Review for external WhatsApp customer onboarding.
