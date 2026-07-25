# Render and Vercel deployment

## Production addresses

- Frontend: `https://kondai-flax.vercel.app`
- Backend: `https://kondai.onrender.com`

## Render environment

```env
ENVIRONMENT=production
FRONTEND_URL=https://kondai-flax.vercel.app
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://kondai-flax.vercel.app
PUBLIC_API_BASE_URL=https://kondai.onrender.com

AUTH_MODE=dev
DEV_USER_ID=booxclash-founder
DEV_WORKSPACE_ID=booxclash-workspace

GITHUB_REDIRECT_URI=
GMAIL_REDIRECT_URI=
```

The blank OAuth redirect variables are generated automatically as:

- `https://kondai.onrender.com/api/v1/integrations/github/oauth/callback`
- `https://kondai.onrender.com/api/v1/integrations/gmail/oauth/callback`

Redeploy Render after changing environment variables.

## Vercel environment

```env
VITE_API_BASE=https://kondai.onrender.com/api/v1
VITE_DEV_USER_ID=booxclash-founder
VITE_DEV_WORKSPACE_ID=booxclash-workspace
```

Vite embeds environment variables during the build. Redeploy Vercel after
saving them.

The frontend API client also contains a safety guard: when the app runs on a
non-local domain, any accidentally deployed `localhost` API base is ignored and
replaced with the Render API address.

## Local development

Backend `backend/.env.local`:

```env
ENVIRONMENT=development
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://kondai-flax.vercel.app
PUBLIC_API_BASE_URL=http://localhost:8000
AUTH_MODE=dev
DEV_USER_ID=local-founder
DEV_WORKSPACE_ID=local-workspace
STORE_MODE=json
AI_MODE=deterministic
OUTBOUND_MODE=mock
GITHUB_REDIRECT_URI=
GMAIL_REDIRECT_URI=
```

Frontend `frontend/.env.local`:

```env
VITE_API_BASE=http://localhost:8000/api/v1
VITE_DEV_USER_ID=local-founder
VITE_DEV_WORKSPACE_ID=local-workspace
```

## Render commands

```text
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /api/v1/health
```

## Vercel commands

```text
Root Directory: frontend
Framework Preset: Vite
Install Command: npm install
Build Command: npm run build
Output Directory: dist
```

## Why production no longer calls localhost

The repository includes:

- `frontend/.env.development` → `http://localhost:8000/api/v1`
- `frontend/.env.production` → `https://kondai.onrender.com/api/v1`

The API client also detects when a non-local browser has been built with a
localhost API address and automatically falls back to Render. This protects the
production deployment even when an old Vercel variable remains configured.

## CORS diagnostics

The application is globally wrapped in `CORSMiddleware`, so successful,
validation, not-found and unexpected-error responses carry CORS headers.

Local check:

```powershell
curl.exe -i -X OPTIONS "http://localhost:8000/api/v1/onboarding/status" `
  -H "Origin: http://localhost:5173" `
  -H "Access-Control-Request-Method: GET" `
  -H "Access-Control-Request-Headers: x-user-id,x-workspace-id,content-type"
```

The response must contain:

```text
access-control-allow-origin: http://localhost:5173
```

Also open:

```text
http://localhost:8000/api/v1/cors-status
```

The response must list both `http://localhost:5173` and
`https://kondai-flax.vercel.app`. If it does not, an old backend process or a
different application is running on port 8000. Stop every Uvicorn process and
start the backend from the `backend` directory with:

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
