# API summary

Base URL:

```text
http://localhost:8000/api/v1
```

Development headers:

```text
X-User-Id: demo-founder
X-Workspace-Id: demo-workspace
```

Main endpoints:

- `GET /health`
- `GET /dashboard`
- `GET/POST /products`
- `POST /products/{id}/analyse`
- `POST /positioning/{id}/approve`
- `GET/POST /prospects`
- `POST /prospects/import`
- `POST /prospects/{id}/qualify`
- `GET/POST /campaigns`
- `POST /campaigns/{id}/prepare`
- `GET /approvals`
- `POST /approvals/{id}/approve`
- `POST /approvals/{id}/reject`
- `POST /approvals/{id}/execute`
- `GET/POST /replies`
- `POST /replies/{id}/classify`
- `POST /briefings/generate`
- `GET /briefings/today`
- `GET /agent-activity`
- `GET /metrics/competition`
