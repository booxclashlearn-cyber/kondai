import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import type {
  GitHubConnectionStatus,
  GitHubRepository,
  OnboardingStatus,
} from "../types";
import { Notice, type NoticeState } from "../components/UI";

type SyncResult = {
  connection: GitHubConnectionStatus;
  product: { id: string; name: string };
  summary: {
    repository: string;
    branch: string;
    file_count: number;
    language_count: number;
    commit_count: number;
    open_issue_count: number;
    manifest_count: number;
  };
};

export function SetupPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [selectedRepository, setSelectedRepository] = useState("");
  const [publicUrl, setPublicUrl] = useState("");
  const [token, setToken] = useState("");
  const [repositorySearch, setRepositorySearch] = useState("");
  const [notice, setNotice] = useState<NoticeState>(null);
  const [busy, setBusy] = useState("");
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);

  const loadStatus = useCallback(async () => {
    const result = await api.get<OnboardingStatus>("/onboarding/status");
    setStatus(result);
    return result;
  }, []);

  const loadRepositories = useCallback(async () => {
    setBusy("repositories");
    try {
      const result = await api.get<GitHubRepository[]>(
        "/integrations/github/repositories",
      );
      setRepositories(result);
      if (result[0] && !selectedRepository) {
        setSelectedRepository(result[0].full_name);
      }
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }, [selectedRepository]);

  useEffect(() => {
    loadStatus()
      .then((result) => {
        if (result.github.account_connected) {
          void loadRepositories();
        }
      })
      .catch((error: Error) =>
        setNotice({ kind: "error", text: error.message }),
      );
  }, [loadRepositories, loadStatus]);

  useEffect(() => {
    const githubResult = searchParams.get("github");
    const message = searchParams.get("message");

    if (githubResult === "connected") {
      setNotice({
        kind: "success",
        text: "GitHub account connected. Choose the repository Kondai should read.",
      });
      setSearchParams({});
      void loadStatus().then(() => loadRepositories());
    }

    if (githubResult === "error") {
      setNotice({
        kind: "error",
        text: message || "GitHub connection failed.",
      });
      setSearchParams({});
    }
  }, [loadRepositories, loadStatus, searchParams, setSearchParams]);

  const filteredRepositories = useMemo(() => {
    const query = repositorySearch.trim().toLowerCase();
    if (!query) return repositories;
    return repositories.filter(
      (repository) =>
        repository.full_name.toLowerCase().includes(query) ||
        (repository.description || "").toLowerCase().includes(query),
    );
  }, [repositories, repositorySearch]);

  async function connectOAuth() {
    setBusy("oauth");
    try {
      const response = await api.post<{ authorization_url: string }>(
        "/integrations/github/oauth/start",
      );
      window.location.assign(response.authorization_url);
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
      setBusy("");
    }
  }

  async function connectToken(event: FormEvent) {
    event.preventDefault();
    setBusy("token");
    try {
      await api.post("/integrations/github/token", { token });
      setToken("");
      setNotice({
        kind: "success",
        text: "GitHub account connected. Choose a repository.",
      });
      await loadStatus();
      await loadRepositories();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }

  async function connectPublicRepository(event: FormEvent) {
    event.preventDefault();
    setBusy("public");
    setSyncResult(null);
    try {
      const result = await api.post<SyncResult>(
        "/integrations/github/public-repository",
        { repository_url: publicUrl },
      );
      setSyncResult(result);
      setNotice({
        kind: "success",
        text: "The public repository was read successfully.",
      });
      await loadStatus();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }

  async function connectSelectedRepository() {
    if (!selectedRepository) {
      setNotice({ kind: "error", text: "Choose a repository first." });
      return;
    }
    setBusy("sync");
    setSyncResult(null);
    try {
      const repository = repositories.find(
        (item) => item.full_name === selectedRepository,
      );
      const result = await api.post<SyncResult>(
        "/integrations/github/repositories/connect",
        {
          full_name: selectedRepository,
          branch: repository?.default_branch || null,
        },
      );
      setSyncResult(result);
      setNotice({
        kind: "success",
        text: "Codebase connected and the initial product workspace was created.",
      });
      await loadStatus();
    } catch (error) {
      setNotice({ kind: "error", text: (error as Error).message });
    } finally {
      setBusy("");
    }
  }

  const github = status?.github;
  const accountConnected = Boolean(github?.account_connected);
  const repositoryConnected = Boolean(github?.repository_connected);

  return (
    <div className="setup-page">
      <header className="setup-header">
        <div className="brand-row setup-brand">
          <div className="brand-mark">K</div>
          <div>
            <h1>Kondai</h1>
            <span>Founder Operations</span>
          </div>
        </div>
        <p>Set up your real workspace</p>
      </header>

      <main className="setup-container">
        <div className="setup-intro">
          <span>Step one</span>
          <h2>Connect the product you are building</h2>
          <p>
            Kondai needs to read your actual repository before it can understand
            your product, prepare accurate campaigns or answer customer questions.
          </p>
        </div>

        <Notice notice={notice} />

        <div className="setup-steps">
          <div className={accountConnected || repositoryConnected ? "done" : "active"}>
            <b>1</b>
            <span>Connect GitHub</span>
          </div>
          <div className={repositoryConnected ? "done" : accountConnected ? "active" : ""}>
            <b>2</b>
            <span>Choose repository</span>
          </div>
          <div className={repositoryConnected ? "done" : ""}>
            <b>3</b>
            <span>Build workspace</span>
          </div>
        </div>

        {!repositoryConnected && (
          <div className="setup-grid">
            <section className="setup-card featured">
              <div className="setup-card-icon">G</div>
              <div>
                <span>Recommended for private repositories</span>
                <h3>Connect your GitHub account</h3>
                <p>
                  Authorize Kondai, then choose one repository from your account
                  or organisation.
                </p>
              </div>
              {accountConnected ? (
                <div className="connected-account">
                  {github?.github_avatar_url && (
                    <img
                      src={github.github_avatar_url}
                      alt=""
                      referrerPolicy="no-referrer"
                    />
                  )}
                  <div>
                    <strong>
                      {github?.github_name || github?.github_login || "GitHub connected"}
                    </strong>
                    <small>@{github?.github_login}</small>
                  </div>
                </div>
              ) : (
                <button disabled={busy === "oauth"} onClick={connectOAuth}>
                  {busy === "oauth" ? "Opening GitHub…" : "Connect with GitHub"}
                </button>
              )}
            </section>

            <section className="setup-card">
              <div className="setup-card-icon">U</div>
              <div>
                <span>No OAuth required</span>
                <h3>Use a public repository URL</h3>
                <p>
                  Paste a public GitHub repository. Kondai will read it directly.
                </p>
              </div>
              <form onSubmit={connectPublicRepository}>
                <input
                  required
                  placeholder="https://github.com/owner/repository"
                  value={publicUrl}
                  onChange={(event) => setPublicUrl(event.target.value)}
                />
                <button disabled={busy === "public"} type="submit">
                  {busy === "public" ? "Reading codebase…" : "Connect public repository"}
                </button>
              </form>
            </section>

            {!accountConnected && (
              <details className="setup-card token-card">
                <summary>Use a personal access token instead</summary>
                <p>
                  Useful during local development. The token is encrypted by the
                  backend and is never returned to the browser.
                </p>
                <form onSubmit={connectToken}>
                  <input
                    required
                    type="password"
                    autoComplete="off"
                    placeholder="github_pat_..."
                    value={token}
                    onChange={(event) => setToken(event.target.value)}
                  />
                  <button disabled={busy === "token"} type="submit">
                    {busy === "token" ? "Verifying token…" : "Connect token"}
                  </button>
                </form>
              </details>
            )}
          </div>
        )}

        {accountConnected && !repositoryConnected && (
          <section className="repository-picker">
            <div className="repository-heading">
              <div>
                <span>Step two</span>
                <h3>Choose the product repository</h3>
                <p>
                  Kondai will read the README, file structure, languages, recent
                  commits, open issues and key configuration files.
                </p>
              </div>
              <button
                className="secondary"
                disabled={busy === "repositories"}
                onClick={() => loadRepositories()}
              >
                Refresh repositories
              </button>
            </div>

            <input
              className="repository-search"
              placeholder="Search repositories…"
              value={repositorySearch}
              onChange={(event) => setRepositorySearch(event.target.value)}
            />

            <div className="repository-list">
              {filteredRepositories.map((repository) => (
                <label
                  className={
                    selectedRepository === repository.full_name
                      ? "repository-option selected"
                      : "repository-option"
                  }
                  key={repository.id}
                >
                  <input
                    type="radio"
                    name="repository"
                    value={repository.full_name}
                    checked={selectedRepository === repository.full_name}
                    onChange={() => setSelectedRepository(repository.full_name)}
                  />
                  <div>
                    <div className="repository-name-row">
                      <strong>{repository.full_name}</strong>
                      <span>{repository.private ? "Private" : "Public"}</span>
                    </div>
                    <p>{repository.description || "No repository description."}</p>
                    <small>
                      {repository.language || "Mixed code"} · updated{" "}
                      {new Date(repository.updated_at).toLocaleDateString()}
                    </small>
                  </div>
                </label>
              ))}
            </div>

            <button
              className="connect-repository-button"
              disabled={!selectedRepository || busy === "sync"}
              onClick={connectSelectedRepository}
            >
              {busy === "sync"
                ? "Reading repository and creating workspace…"
                : "Use this repository"}
            </button>
          </section>
        )}

        {repositoryConnected && (
          <section className="setup-complete">
            <div className="success-check">✓</div>
            <span>Workspace ready</span>
            <h2>{github?.selected_repository}</h2>
            <p>
              Kondai has read the codebase and created the initial product
              workspace. Revenue, analytics and customer integrations can now be
              added from Connections.
            </p>

            {syncResult && (
              <div className="sync-summary">
                <div><strong>{syncResult.summary.file_count}</strong><span>Files indexed</span></div>
                <div><strong>{syncResult.summary.language_count}</strong><span>Languages</span></div>
                <div><strong>{syncResult.summary.commit_count}</strong><span>Recent commits</span></div>
                <div><strong>{syncResult.summary.open_issue_count}</strong><span>Open issues</span></div>
                <div><strong>{syncResult.summary.manifest_count}</strong><span>Key files read</span></div>
              </div>
            )}

            <button onClick={() => navigate("/")}>Open Kondai</button>
          </section>
        )}

        {busy === "sync" || busy === "public" ? (
          <div className="sync-progress">
            <div className="setup-spinner" />
            <div>
              <strong>Building your product workspace</strong>
              <p>
                Reading repository metadata, README, file tree, languages,
                commits, issues and key manifests.
              </p>
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
}
