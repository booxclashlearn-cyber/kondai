from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlparse

import httpx

from app.core.config import get_settings
from app.core.repository import get_repository, utc_now
from app.services.audit_service import log_agent_run
from app.services.knowledge_graph_service import knowledge_graph
from app.services.secret_service import secret_service


GITHUB_API = "https://api.github.com"
GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_ACCESS_TOKEN = "https://github.com/login/oauth/access_token"

TEXT_FILE_NAMES = {
    "readme.md",
    "readme",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "poetry.lock",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "firebase.json",
    "vercel.json",
    "render.yaml",
    "fly.toml",
    "vite.config.ts",
    "vite.config.js",
    "next.config.js",
    "next.config.mjs",
    "tsconfig.json",
    "tailwind.config.js",
    "tailwind.config.ts",
    "go.mod",
    "cargo.toml",
    "gemfile",
    "composer.json",
}

TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
}


def _decode_workspace(encoded: str) -> str:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(f"{encoded}{padding}").decode("utf-8")


def _encode_workspace(workspace_id: str) -> str:
    return base64.urlsafe_b64encode(
        workspace_id.encode("utf-8")
    ).decode("utf-8").rstrip("=")


def _parse_repository(value: str) -> str:
    raw = value.strip().rstrip("/")
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise ValueError("Only github.com repository URLs are supported.")
        raw = parsed.path.strip("/")
    if raw.endswith(".git"):
        raw = raw[:-4]
    parts = [part for part in raw.split("/") if part]
    if len(parts) != 2:
        raise ValueError(
            "Enter a repository as owner/repository or a full GitHub repository URL."
        )
    return f"{parts[0]}/{parts[1]}"


class GitHubService:
    def __init__(self) -> None:
        self.repo = get_repository()
        self.settings = get_settings()

    def _headers(self, token: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.settings.github_api_version,
            "User-Agent": "Kondai-Founder-Operations",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _get_connection(self, workspace_id: str) -> dict[str, Any] | None:
        return self.repo.get(
            "integration_connections",
            "github",
            workspace_id,
        )

    def _save_connection(
        self,
        workspace_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        current = self._get_connection(workspace_id)
        safe_payload = {
            **payload,
            "id": "github",
            "provider": "github",
        }
        if current:
            return self.repo.update(
                "integration_connections",
                "github",
                workspace_id,
                safe_payload,
            ) or current
        return self.repo.create(
            "integration_connections",
            workspace_id,
            safe_payload,
        )

    def _connection_token(self, workspace_id: str) -> str | None:
        connection = self._get_connection(workspace_id)
        encrypted = (connection or {}).get("encrypted_access_token")
        if not encrypted:
            return None
        return secret_service.decrypt(encrypted)

    def start_oauth(
        self,
        workspace_id: str,
        user_id: str,
    ) -> dict[str, str]:
        if not self.settings.github_client_id:
            raise RuntimeError(
                "GitHub OAuth is not configured. Add GITHUB_CLIENT_ID and "
                "GITHUB_CLIENT_SECRET to backend/.env, or use a public repository "
                "URL or personal access token."
            )

        random_part = secrets.token_urlsafe(32)
        encoded_workspace = _encode_workspace(workspace_id)
        state = f"{encoded_workspace}.{random_part}"
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=10)
        ).isoformat()

        self.repo.create(
            "oauth_states",
            workspace_id,
            {
                "id": state,
                "provider": "github",
                "user_id": user_id,
                "expires_at": expires_at,
            },
        )

        query = urlencode(
            {
                "client_id": self.settings.github_client_id,
                "redirect_uri": self.settings.github_redirect_uri,
                "scope": self.settings.github_oauth_scope,
                "state": state,
                "allow_signup": "true",
            }
        )
        return {"authorization_url": f"{GITHUB_AUTHORIZE}?{query}"}

    async def complete_oauth(
        self,
        code: str,
        state: str,
    ) -> tuple[str, str]:
        try:
            encoded_workspace = state.split(".", 1)[0]
            workspace_id = _decode_workspace(encoded_workspace)
        except Exception as exc:
            raise ValueError("Invalid GitHub OAuth state.") from exc

        state_record = self.repo.get(
            "oauth_states",
            state,
            workspace_id,
        )
        if not state_record:
            raise ValueError("GitHub OAuth state was not found or was already used.")

        expires_at = datetime.fromisoformat(state_record["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            self.repo.delete("oauth_states", state, workspace_id)
            raise ValueError("GitHub OAuth state expired. Start the connection again.")

        if not self.settings.github_client_secret:
            raise RuntimeError("GITHUB_CLIENT_SECRET is not configured.")

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            token_response = await client.post(
                GITHUB_ACCESS_TOKEN,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Kondai-Founder-Operations",
                },
                data={
                    "client_id": self.settings.github_client_id,
                    "client_secret": self.settings.github_client_secret,
                    "code": code,
                    "redirect_uri": self.settings.github_redirect_uri,
                    "state": state,
                },
            )
            token_response.raise_for_status()
            token_payload = token_response.json()

            access_token = token_payload.get("access_token")
            if not access_token:
                description = token_payload.get(
                    "error_description",
                    token_payload.get("error", "GitHub did not return an access token."),
                )
                raise ValueError(str(description))

            user_response = await client.get(
                f"{GITHUB_API}/user",
                headers=self._headers(access_token),
            )
            user_response.raise_for_status()
            github_user = user_response.json()

        self._save_connection(
            workspace_id,
            {
                "status": "account_connected",
                "connection_type": "oauth",
                "encrypted_access_token": secret_service.encrypt(access_token),
                "github_user_id": github_user.get("id"),
                "github_login": github_user.get("login"),
                "github_name": github_user.get("name"),
                "github_avatar_url": github_user.get("avatar_url"),
                "connected_by": state_record.get("user_id"),
                "connected_at": utc_now(),
                "selected_repository": None,
                "last_synced_at": None,
            },
        )
        self.repo.delete("oauth_states", state, workspace_id)

        log_agent_run(
            workspace_id,
            "integration_service",
            "github_account_connected",
            f"Connected GitHub account {github_user.get('login', '')}.",
            {"mode": "live_api", "provider": "github"},
            {},
            5,
        )
        return workspace_id, str(github_user.get("login", ""))

    async def connect_token(
        self,
        workspace_id: str,
        user_id: str,
        token: str,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{GITHUB_API}/user",
                headers=self._headers(token),
            )
            if response.status_code == 401:
                raise ValueError("GitHub rejected the personal access token.")
            response.raise_for_status()
            github_user = response.json()

        connection = self._save_connection(
            workspace_id,
            {
                "status": "account_connected",
                "connection_type": "personal_access_token",
                "encrypted_access_token": secret_service.encrypt(token),
                "github_user_id": github_user.get("id"),
                "github_login": github_user.get("login"),
                "github_name": github_user.get("name"),
                "github_avatar_url": github_user.get("avatar_url"),
                "connected_by": user_id,
                "connected_at": utc_now(),
                "selected_repository": None,
                "last_synced_at": None,
            },
        )
        return self.public_status(workspace_id, connection)

    async def list_repositories(
        self,
        workspace_id: str,
    ) -> list[dict[str, Any]]:
        token = self._connection_token(workspace_id)
        if not token:
            raise ValueError(
                "Connect a GitHub account before requesting private repositories."
            )

        repositories: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=40) as client:
            for page in range(1, 4):
                response = await client.get(
                    f"{GITHUB_API}/user/repos",
                    headers=self._headers(token),
                    params={
                        "per_page": 100,
                        "page": page,
                        "sort": "updated",
                        "direction": "desc",
                        "affiliation": "owner,collaborator,organization_member",
                    },
                )
                response.raise_for_status()
                items = response.json()
                for item in items:
                    repositories.append(
                        {
                            "id": item.get("id"),
                            "full_name": item.get("full_name"),
                            "name": item.get("name"),
                            "description": item.get("description"),
                            "private": item.get("private", False),
                            "default_branch": item.get("default_branch"),
                            "language": item.get("language"),
                            "updated_at": item.get("updated_at"),
                            "html_url": item.get("html_url"),
                            "owner_avatar_url": (
                                item.get("owner") or {}
                            ).get("avatar_url"),
                        }
                    )
                if len(items) < 100:
                    break
        return repositories

    async def connect_public_repository(
        self,
        workspace_id: str,
        user_id: str,
        repository_url: str,
    ) -> dict[str, Any]:
        full_name = _parse_repository(repository_url)
        return await self.sync_repository(
            workspace_id=workspace_id,
            user_id=user_id,
            full_name=full_name,
            branch=None,
            force_public=True,
        )

    async def sync_repository(
        self,
        workspace_id: str,
        user_id: str,
        full_name: str,
        branch: str | None,
        force_public: bool = False,
    ) -> dict[str, Any]:
        full_name = _parse_repository(full_name)
        token = None if force_public else self._connection_token(workspace_id)

        repository = await self._fetch_repository(full_name, token)
        if repository.get("private") and not token:
            raise ValueError(
                "This repository is private. Connect GitHub or provide a token first."
            )

        selected_branch = branch or repository.get("default_branch") or "main"
        snapshot = await self._read_codebase(
            full_name=full_name,
            branch=selected_branch,
            token=token,
            repository=repository,
        )

        product = self._upsert_product(
            workspace_id=workspace_id,
            repository=repository,
            snapshot=snapshot,
        )

        previous_sources = [
            item
            for item in self.repo.list("sources", workspace_id)
            if item.get("source_type") == "github"
            and item.get("external_id") == full_name
        ]
        for source in previous_sources:
            self.repo.update(
                "sources",
                source["id"],
                workspace_id,
                {"status": "superseded"},
            )

        ingestion = knowledge_graph.ingest(
            workspace_id=workspace_id,
            source_type="github",
            name=f"GitHub repository: {full_name}",
            data=snapshot,
            external_id=full_name,
            product_id=product["id"],
        )

        existing_connection = self._get_connection(workspace_id) or {}
        connection_payload = {
            "status": "repository_connected",
            "connection_type": (
                existing_connection.get("connection_type")
                or ("public_repository" if not token else "account")
            ),
            "selected_repository": full_name,
            "selected_branch": selected_branch,
            "repository_private": bool(repository.get("private")),
            "repository_html_url": repository.get("html_url"),
            "repository_description": repository.get("description"),
            "product_id": product["id"],
            "source_id": ingestion["source"]["id"],
            "last_synced_at": utc_now(),
            "connected_by": user_id,
        }
        if existing_connection.get("encrypted_access_token"):
            connection_payload["encrypted_access_token"] = existing_connection[
                "encrypted_access_token"
            ]
        for key in (
            "github_user_id",
            "github_login",
            "github_name",
            "github_avatar_url",
            "connected_at",
        ):
            if existing_connection.get(key) is not None:
                connection_payload[key] = existing_connection[key]

        connection = self._save_connection(
            workspace_id,
            connection_payload,
        )

        log_agent_run(
            workspace_id,
            "integration_service",
            "github_repository_synced",
            (
                f"Read {snapshot['file_count']} files from {full_name} and "
                f"created the initial product workspace."
            ),
            {
                "mode": "live_api",
                "provider": "github",
                "branch": selected_branch,
            },
            {
                "repository": full_name,
                "product_id": product["id"],
                "source_id": ingestion["source"]["id"],
            },
            35,
        )

        return {
            "connection": self.public_status(workspace_id, connection),
            "product": product,
            "summary": {
                "repository": full_name,
                "branch": selected_branch,
                "file_count": snapshot["file_count"],
                "language_count": len(snapshot["languages"]),
                "commit_count": len(snapshot["commits"]),
                "open_issue_count": snapshot["open_bugs"],
                "manifest_count": len(snapshot["manifests"]),
            },
        }

    async def _fetch_repository(
        self,
        full_name: str,
        token: str | None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{GITHUB_API}/repos/{full_name}",
                headers=self._headers(token),
            )
            if response.status_code == 404:
                raise ValueError(
                    "Repository not found or the connected account cannot access it."
                )
            response.raise_for_status()
            return response.json()

    async def _read_codebase(
        self,
        full_name: str,
        branch: str,
        token: str | None,
        repository: dict[str, Any],
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=45) as client:
            readme_response = await client.get(
                f"{GITHUB_API}/repos/{full_name}/readme",
                headers=self._headers(token),
                params={"ref": branch},
            )
            readme = ""
            if readme_response.status_code == 200:
                readme_payload = readme_response.json()
                readme = self._decode_content(readme_payload)[:50000]

            tree_response = await client.get(
                f"{GITHUB_API}/repos/{full_name}/git/trees/{quote(branch, safe='')}",
                headers=self._headers(token),
                params={"recursive": "1"},
            )
            tree_response.raise_for_status()
            tree_payload = tree_response.json()
            tree = [
                item
                for item in tree_payload.get("tree", [])
                if item.get("type") == "blob"
            ][: self.settings.github_sync_file_limit]

            languages_response = await client.get(
                f"{GITHUB_API}/repos/{full_name}/languages",
                headers=self._headers(token),
            )
            languages = (
                languages_response.json()
                if languages_response.status_code == 200
                else {}
            )

            commits_response = await client.get(
                f"{GITHUB_API}/repos/{full_name}/commits",
                headers=self._headers(token),
                params={"sha": branch, "per_page": 20},
            )
            commits_payload = (
                commits_response.json()
                if commits_response.status_code == 200
                else []
            )
            commits = [
                {
                    "sha": item.get("sha"),
                    "message": (
                        (item.get("commit") or {}).get("message") or ""
                    ).splitlines()[0][:300],
                    "author": (
                        ((item.get("commit") or {}).get("author") or {}).get("name")
                    ),
                    "date": (
                        ((item.get("commit") or {}).get("author") or {}).get("date")
                    ),
                    "html_url": item.get("html_url"),
                }
                for item in commits_payload
            ]

            issues_response = await client.get(
                f"{GITHUB_API}/repos/{full_name}/issues",
                headers=self._headers(token),
                params={"state": "open", "per_page": 30},
            )
            issue_payload = (
                issues_response.json()
                if issues_response.status_code == 200
                else []
            )
            issues = [
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "labels": [
                        label.get("name")
                        for label in item.get("labels", [])
                        if isinstance(label, dict)
                    ],
                    "html_url": item.get("html_url"),
                }
                for item in issue_payload
                if "pull_request" not in item
            ]

            manifest_paths = self._choose_text_files(tree)
            manifests: dict[str, str] = {}
            for path in manifest_paths:
                content_response = await client.get(
                    f"{GITHUB_API}/repos/{full_name}/contents/{quote(path, safe='/')}",
                    headers=self._headers(token),
                    params={"ref": branch},
                )
                if content_response.status_code != 200:
                    continue
                content_payload = content_response.json()
                content = self._decode_content(content_payload)
                if content:
                    manifests[path] = content[:30000]

        file_paths = [item.get("path", "") for item in tree]
        return {
            "repository": full_name,
            "description": repository.get("description") or "",
            "homepage": repository.get("homepage") or "",
            "html_url": repository.get("html_url") or "",
            "private": bool(repository.get("private")),
            "default_branch": branch,
            "readme": readme,
            "languages": languages,
            "file_count": len(file_paths),
            "tree_truncated": bool(tree_payload.get("truncated")),
            "file_tree": file_paths,
            "manifests": manifests,
            "recent_commits": len(commits),
            "commits": commits,
            "recent_features": [
                item["message"]
                for item in commits[:10]
                if item.get("message")
            ],
            "open_bugs": len(issues),
            "issues": issues,
            "critical_issues": [
                item["title"]
                for item in issues[:10]
                if item.get("title")
            ],
            "synced_at": utc_now(),
        }

    def _choose_text_files(
        self,
        tree: list[dict[str, Any]],
    ) -> list[str]:
        candidates: list[tuple[int, str]] = []
        for item in tree:
            path = str(item.get("path") or "")
            if not path:
                continue
            size = int(item.get("size") or 0)
            if size > self.settings.github_sync_file_size_limit:
                continue
            lower = path.lower()
            name = lower.rsplit("/", 1)[-1]
            extension = f".{name.rsplit('.', 1)[-1]}" if "." in name else ""

            priority = None
            if name in TEXT_FILE_NAMES:
                priority = 0
            elif lower.startswith("docs/") and extension in TEXT_EXTENSIONS:
                priority = 1
            elif extension in {".md", ".json", ".toml", ".yaml", ".yml"}:
                priority = 2

            if priority is not None:
                candidates.append((priority, path))

        candidates.sort(key=lambda item: (item[0], len(item[1]), item[1]))
        return [
            path
            for _, path in candidates[
                : self.settings.github_sync_manifest_limit
            ]
        ]

    @staticmethod
    def _decode_content(payload: dict[str, Any]) -> str:
        if payload.get("encoding") != "base64":
            return ""
        encoded = str(payload.get("content") or "").replace("\n", "")
        try:
            return base64.b64decode(encoded).decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _upsert_product(
        self,
        workspace_id: str,
        repository: dict[str, Any],
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        full_name = str(repository.get("full_name") or "")
        existing = next(
            (
                item
                for item in self.repo.list("products", workspace_id)
                if item.get("github_repository") == full_name
            ),
            None,
        )

        description = str(repository.get("description") or "").strip()
        if not description:
            readme = str(snapshot.get("readme") or "").strip()
            description = (
                readme[:1500]
                if readme
                else f"Software product contained in {full_name}."
            )

        payload = {
            "name": repository.get("name") or full_name.split("/")[-1],
            "description": description,
            "url": (
                repository.get("homepage")
                or repository.get("html_url")
                or ""
            ),
            "category": "Software",
            "stage": "connected_codebase",
            "pricing": "",
            "target_customer": "",
            "primary_goal": "Complete product setup and connect business data.",
            "github_repository": full_name,
            "github_branch": snapshot.get("default_branch"),
            "codebase_connected_at": utc_now(),
        }

        if existing:
            return self.repo.update(
                "products",
                existing["id"],
                workspace_id,
                payload,
            ) or existing
        return self.repo.create("products", workspace_id, payload)

    def public_status(
        self,
        workspace_id: str,
        connection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        connection = connection or self._get_connection(workspace_id)
        if not connection:
            return {
                "connected": False,
                "repository_connected": False,
                "status": "not_connected",
                "github_login": None,
                "github_name": None,
                "github_avatar_url": None,
                "selected_repository": None,
                "selected_branch": None,
                "repository_private": None,
                "repository_html_url": None,
                "last_synced_at": None,
            }
        return {
            "connected": bool(connection.get("encrypted_access_token"))
            or connection.get("connection_type") == "public_repository",
            "account_connected": bool(connection.get("encrypted_access_token")),
            "repository_connected": (
                connection.get("status") == "repository_connected"
                and bool(connection.get("selected_repository"))
            ),
            "status": connection.get("status", "not_connected"),
            "connection_type": connection.get("connection_type"),
            "github_login": connection.get("github_login"),
            "github_name": connection.get("github_name"),
            "github_avatar_url": connection.get("github_avatar_url"),
            "selected_repository": connection.get("selected_repository"),
            "selected_branch": connection.get("selected_branch"),
            "repository_private": connection.get("repository_private"),
            "repository_html_url": connection.get("repository_html_url"),
            "repository_description": connection.get("repository_description"),
            "last_synced_at": connection.get("last_synced_at"),
            "product_id": connection.get("product_id"),
        }

    def onboarding_status(self, workspace_id: str) -> dict[str, Any]:
        github = self.public_status(workspace_id)
        repository_connected = bool(github["repository_connected"])
        if repository_connected:
            current_step = "complete"
        elif github.get("account_connected"):
            current_step = "select_repository"
        else:
            current_step = "connect_codebase"

        return {
            "complete": repository_connected,
            "current_step": current_step,
            "github": github,
        }

    def disconnect(self, workspace_id: str) -> bool:
        connection = self._get_connection(workspace_id)
        if not connection:
            return False
        return self.repo.delete(
            "integration_connections",
            "github",
            workspace_id,
        )


github_service = GitHubService()
