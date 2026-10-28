const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";
const ACCESS_KEY = "cf_access";
const REFRESH_KEY = "cf_refresh";

// NOTE: tokens live in localStorage for simplicity in this portfolio demo. For production, prefer an
// httpOnly, SameSite cookie issued by the backend (see "Deployment notes" in the README).
export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export const LOGOUT_EVENT = "cf:logout";

export class ApiError extends Error {
  status: number;
  fieldErrors: Record<string, string[]>;
  nonFieldErrors: string[];

  constructor(status: number, body: unknown) {
    const { message, fieldErrors, nonFieldErrors } = parseErrorBody(status, body);
    super(message);
    this.status = status;
    this.fieldErrors = fieldErrors;
    this.nonFieldErrors = nonFieldErrors;
  }
}

function toList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((v) => (typeof v === "string" ? v : JSON.stringify(v)));
  if (typeof value === "string") return [value];
  return [];
}

function parseErrorBody(status: number, body: unknown) {
  const fieldErrors: Record<string, string[]> = {};
  let nonFieldErrors: string[] = [];
  if (body && typeof body === "object") {
    for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
      if (key === "detail" || key === "non_field_errors") nonFieldErrors = nonFieldErrors.concat(toList(value));
      else fieldErrors[key] = toList(value);
    }
  }
  const first = Object.entries(fieldErrors)[0];
  const message =
    nonFieldErrors[0] ??
    (first ? `${first[0].replace(/_/g, " ")}: ${first[1][0]}` : undefined) ??
    (status === 0 ? "Cannot reach the server. Check your connection." : `Request failed (${status}).`);
  return { message, fieldErrors, nonFieldErrors };
}

export type Params = Record<string, string | number | boolean | null | undefined>;

function buildUrl(path: string, params?: Params) {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  }
  return url.pathname + url.search;
}

let refreshing: Promise<boolean> | null = null;

async function refreshAccess(): Promise<boolean> {
  const refresh = tokens.refresh;
  if (!refresh) return false;
  refreshing ??= fetch(`${BASE}/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  })
    .then(async (res) => {
      if (!res.ok) return false;
      const data = (await res.json()) as { access: string; refresh?: string };
      tokens.set(data.access, data.refresh);
      return true;
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

type FetchInit = RequestInit & { params?: Params; auth?: boolean };

async function rawFetch(path: string, init: FetchInit = {}): Promise<Response> {
  const { params, auth = true, ...rest } = init;
  const send = () => {
    const headers = new Headers(rest.headers);
    if (rest.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (auth && tokens.access) headers.set("Authorization", `Bearer ${tokens.access}`);
    return fetch(buildUrl(path, params), { ...rest, headers });
  };
  let res: Response;
  try {
    res = await send();
  } catch {
    throw new ApiError(0, null);
  }
  if (res.status === 401 && auth && tokens.refresh) {
    if (await refreshAccess()) {
      res = await send();
    } else {
      tokens.clear();
      window.dispatchEvent(new Event(LOGOUT_EVENT));
    }
  }
  return res;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function request<T>(path: string, init: FetchInit = {}): Promise<T> {
  const res = await rawFetch(path, init);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const body = text ? safeJson(text) : null;
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

export const api = {
  get: <T>(path: string, params?: Params) => request<T>(path, { params }),
  post: <T>(path: string, data?: unknown, auth = true) =>
    request<T>(path, { method: "POST", body: data === undefined ? undefined : JSON.stringify(data), auth }),
  patch: <T>(path: string, data: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (path: string) => request<void>(path, { method: "DELETE" }),
};

/** Download a list endpoint's CSV export (same filters as the table) through an authenticated request. */
export async function downloadCsv(resource: string, params?: Params) {
  const res = await rawFetch(`/${resource}/export/`, { params });
  if (!res.ok) throw new ApiError(res.status, null);
  const blob = await res.blob();
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? `${resource}.csv`;
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(href);
}
