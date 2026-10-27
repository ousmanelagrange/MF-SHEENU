// Client HTTP : jetons, rafraîchissement automatique, famille courante.

export const API_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ??
  "http://localhost:8000";

const K_ACCESS = "sheenu.access";
const K_REFRESH = "sheenu.refresh";
const K_FAMILY = "sheenu.family";

export const session = {
  get access() {
    return localStorage.getItem(K_ACCESS);
  },
  get refresh() {
    return localStorage.getItem(K_REFRESH);
  },
  get familyId() {
    return localStorage.getItem(K_FAMILY);
  },
  setTokens(access: string, refresh: string) {
    localStorage.setItem(K_ACCESS, access);
    localStorage.setItem(K_REFRESH, refresh);
  },
  setFamily(id: string | null) {
    if (id) localStorage.setItem(K_FAMILY, id);
    else localStorage.removeItem(K_FAMILY);
  },
  clear() {
    localStorage.removeItem(K_ACCESS);
    localStorage.removeItem(K_REFRESH);
    localStorage.removeItem(K_FAMILY);
  },
};

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const token = session.refresh;
  if (!token) return false;
  refreshing ??= fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: token }),
  })
    .then(async (r) => {
      if (!r.ok) return false;
      const data = await r.json();
      session.setTokens(data.access_token, data.refresh_token);
      return true;
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

type Options = {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  raw?: boolean;
  form?: FormData;
  family?: boolean;
};

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const url = new URL(`${API_URL}/api/v1${path}`);
  for (const [k, v] of Object.entries(opts.query ?? {})) {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  }

  const send = () => {
    const headers: Record<string, string> = {};
    if (session.access) headers.Authorization = `Bearer ${session.access}`;
    if (opts.family !== false && session.familyId) headers["X-Family-Id"] = session.familyId;
    let body: BodyInit | undefined;
    if (opts.form) body = opts.form;
    else if (opts.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.body);
    }
    return fetch(url, { method: opts.method ?? "GET", headers, body });
  };

  let res = await send();
  if (res.status === 401 && session.refresh && (await tryRefresh())) res = await send();

  if (!res.ok) {
    let code = "error";
    let message = `Erreur ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail?.code) {
        code = data.detail.code;
        message = data.detail.message;
      } else if (Array.isArray(data?.detail)) {
        code = "validation_error";
        message = data.detail.map((d: { msg: string }) => d.msg).join(" ");
      }
    } catch {
      /* corps non JSON */
    }
    throw new ApiError(res.status, code, message);
  }
  if (opts.raw) return res as unknown as T;
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
