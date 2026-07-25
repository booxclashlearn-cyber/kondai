type ApiRequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

type ValidationError = {
  loc?: Array<string | number>;
  msg?: string;
};

const LOCAL_API_BASE = "http://localhost:8000/api/v1";
const PRODUCTION_API_BASE = "https://kondai.onrender.com/api/v1";

function isLocalBrowser(): boolean {
  return (
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1"
  );
}

function isLoopbackUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.hostname === "localhost" || url.hostname === "127.0.0.1";
  } catch {
    return false;
  }
}

function resolveApiBase(): string {
  const configured = import.meta.env.VITE_API_BASE?.trim().replace(/\/+$/, "");
  const localBrowser = isLocalBrowser();

  // A production browser can never reach the visitor's localhost backend.
  // Ignore an accidentally deployed localhost VITE_API_BASE and use Render.
  if (!localBrowser && configured && isLoopbackUrl(configured)) {
    console.warn(
      "Kondai ignored a localhost VITE_API_BASE in production and switched to Render.",
    );
    return PRODUCTION_API_BASE;
  }

  if (configured) {
    return configured;
  }

  return localBrowser ? LOCAL_API_BASE : PRODUCTION_API_BASE;
}

export const API_BASE = resolveApiBase();

function buildHeaders(body: unknown, incoming?: HeadersInit): Headers {
  const headers = new Headers(incoming);
  headers.set("Accept", "application/json");

  if (body !== undefined && !(body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const devUserId = import.meta.env.VITE_DEV_USER_ID?.trim();
  const devWorkspaceId = import.meta.env.VITE_DEV_WORKSPACE_ID?.trim();

  if (devUserId) {
    headers.set("X-User-Id", devUserId);
  }

  if (devWorkspaceId) {
    headers.set("X-Workspace-Id", devWorkspaceId);
  }

  return headers;
}

function formatError(payload: unknown, status: number): string {
  if (!payload || typeof payload !== "object") {
    return `Request failed (${status})`;
  }

  const detail = (payload as { detail?: unknown }).detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) => {
        if (!item || typeof item !== "object") {
          return String(item);
        }

        const error = item as ValidationError;
        const location = (error.loc ?? [])
          .filter((part) => part !== "body")
          .join(".");

        return location
          ? `${location}: ${error.msg ?? "Invalid value"}`
          : error.msg ?? "Invalid value";
      })
      .join(" | ");
  }

  return `Request failed (${status})`;
}

async function request<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const { body, headers: incomingHeaders, ...requestOptions } = options;
  const headers = buildHeaders(body, incomingHeaders);

  const response = await fetch(`${API_BASE}${normalizedPath}`, {
    ...requestOptions,
    headers,
    mode: "cors",
    // Kondai currently uses explicit auth/workspace headers, not cookies.
    credentials: "omit",
    body:
      body === undefined
        ? undefined
        : body instanceof FormData
          ? body
          : JSON.stringify(body),
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const payload: unknown = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text();

  if (!response.ok) {
    throw new Error(formatError(payload, response.status));
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string) =>
    request<T>(path, {
      method: "GET",
    }),

  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body,
    }),

  put: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "PUT",
      body,
    }),

  patch: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body,
    }),

  delete: <T>(path: string) =>
    request<T>(path, {
      method: "DELETE",
    }),
};
