// Client HTTP mobile : jetons conservés sur l'appareil, rafraîchissement automatique, famille courante,
// et cache hors connexion : les dernières réponses des écrans de lecture sont gardées sur le
// téléphone et réaffichées quand le réseau manque (ENF-04). Les envois faits hors connexion
// passent par la file d'attente de sync.ts, qui les rejoue au retour du réseau.

import AsyncStorage from "@react-native-async-storage/async-storage";

// En développement sur téléphone, remplacez par l'adresse IP de votre ordinateur.
export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const K = { access: "sheenu.access", refresh: "sheenu.refresh", family: "sheenu.family" };
let cache: { access: string | null; refresh: string | null; family: string | null } = {
  access: null,
  refresh: null,
  family: null,
};

export const session = {
  async load() {
    const [access, refresh, family] = await Promise.all([
      AsyncStorage.getItem(K.access),
      AsyncStorage.getItem(K.refresh),
      AsyncStorage.getItem(K.family),
    ]);
    cache = { access, refresh, family };
    return cache;
  },
  get access() {
    return cache.access;
  },
  get family() {
    return cache.family;
  },
  async setTokens(access: string, refresh: string) {
    cache.access = access;
    cache.refresh = refresh;
    await AsyncStorage.multiSet([
      [K.access, access],
      [K.refresh, refresh],
    ]);
  },
  async setFamily(id: string | null) {
    cache.family = id;
    if (id) await AsyncStorage.setItem(K.family, id);
    else await AsyncStorage.removeItem(K.family);
  },
  async clear() {
    cache = { access: null, refresh: null, family: null };
    // Les données familiales mises en cache partent avec la session
    const keys = (await AsyncStorage.getAllKeys()).filter((k) => k.startsWith("sheenu.cache."));
    await AsyncStorage.multiRemove([K.access, K.refresh, K.family, ...keys]);
  },
};

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

// Un seul rafraîchissement à la fois : le jeton de rafraîchissement change à chaque usage
// (rotation), deux demandes simultanées avec le même jeton ressembleraient à un vol.
let refreshing: Promise<boolean> | null = null;

export function refresh(): Promise<boolean> {
  if (!cache.refresh) return Promise.resolve(false);
  refreshing ??= fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: cache.refresh }),
  })
    .then(async (r) => {
      if (!r.ok) return false;
      const t = await r.json();
      await session.setTokens(t.access_token, t.refresh_token);
      return true;
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/** fetch avec délai maximal : sur un réseau qui ne répond plus, on bascule hors connexion. */
function fetchWithTimeout(url: string, init: RequestInit, ms = 15_000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  return fetch(url, { ...init, signal: controller.signal }).finally(() => clearTimeout(timer));
}

// ---------- Cache hors connexion ----------

/** Écrans relus hors connexion. Les actions (POST, PATCH…) ne sont jamais rejouées. */
const CACHED = ["/families", "/persons", "/tree", "/feed", "/posts", "/stories", "/proposals", "/narratives", "/albums", "/timeline", "/contributions/events", "/diaspora", "/notifications"];
const cacheKey = (url: string) => `sheenu.cache.${cache.family ?? "-"}.${url}`;

let offline = false;
const listeners = new Set<(offline: boolean) => void>();
export function setOffline(value: boolean) {
  if (value === offline) return;
  offline = value;
  listeners.forEach((l) => l(value));
}
export const isOffline = () => offline;

/** Le serveur répond-il ? (appelé régulièrement tant qu'on est hors connexion) */
export async function ping(): Promise<boolean> {
  try {
    const r = await fetchWithTimeout(`${API_URL}/health`, {}, 5_000);
    setOffline(!r.ok);
    return r.ok;
  } catch {
    setOffline(true);
    return false;
  }
}

function buildUrl(path: string, query?: Record<string, string | number | undefined>) {
  const qs = Object.entries(query ?? {})
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");
  return `${API_URL}/api/v1${path}${qs ? `?${qs}` : ""}`;
}

/** Dernière réponse gardée pour cette adresse (lecture hors connexion), ou null. */
export async function readCache<T>(path: string, query?: Record<string, string | number | undefined>): Promise<T | null> {
  const saved = await AsyncStorage.getItem(cacheKey(buildUrl(path, query))).catch(() => null);
  return saved ? (JSON.parse(saved) as T) : null;
}
/** S'abonner au passage hors connexion / en ligne ; renvoie la fonction de désabonnement. */
export function onConnectivity(listener: (offline: boolean) => void) {
  listeners.add(listener);
  return () => void listeners.delete(listener);
}

export type ApiOptions = {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | undefined>;
  family?: string | null; // famille visée, si ce n'est pas la famille courante (rejeu de la file)
  idempotencyKey?: string; // rend l'envoi rejouable sans doublon
};

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const url = buildUrl(path, opts.query);
  const method = opts.method ?? "GET";
  const cacheable = method === "GET" && CACHED.some((prefix) => path.startsWith(prefix));
  const send = () => {
    const headers: Record<string, string> = {};
    if (cache.access) headers.Authorization = `Bearer ${cache.access}`;
    const family = opts.family !== undefined ? opts.family : cache.family;
    if (family) headers["X-Family-Id"] = family;
    if (opts.idempotencyKey) headers["Idempotency-Key"] = opts.idempotencyKey;
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    return fetchWithTimeout(url, {
      method,
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  };

  let res: Response;
  try {
    res = await send();
    if (res.status === 401 && (await refresh())) res = await send();
    setOffline(false);
  } catch {
    // Pas de réseau : on ressert la dernière réponse connue, s'il y en a une
    setOffline(true);
    const saved = cacheable ? await AsyncStorage.getItem(cacheKey(url)) : null;
    if (saved) return JSON.parse(saved) as T;
    throw new ApiError(0, "offline", "Pas de connexion. Réessayez quand le réseau revient.");
  }
  if (!res.ok) {
    let code = "error";
    let message = `Erreur ${res.status}`;
    try {
      const d = await res.json();
      if (d?.detail?.code) {
        code = d.detail.code;
        message = d.detail.message;
      }
    } catch {
      /* corps non JSON */
    }
    throw new ApiError(res.status, code, message);
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json();
  if (cacheable) void AsyncStorage.setItem(cacheKey(url), JSON.stringify(data)).catch(() => undefined);
  return data;
}

/** Envoie une photo choisie sur l'appareil (expo-image-picker) et renvoie son adresse. */
export async function uploadImage(asset: { uri: string; mimeType?: string | null; fileName?: string | null }): Promise<string> {
  const form = new FormData();
  const name = asset.fileName ?? "photo.jpg";
  const type = asset.mimeType ?? "image/jpeg";
  if (asset.uri.startsWith("blob:") || asset.uri.startsWith("data:")) {
    // Version web : l'image est déjà dans le navigateur
    form.append("file", await (await fetch(asset.uri)).blob(), name);
  } else {
    // iOS / Android : React Native lit le fichier à partir de son adresse locale
    form.append("file", { uri: asset.uri, name, type } as unknown as Blob);
  }
  const headers: Record<string, string> = {};
  if (cache.access) headers.Authorization = `Bearer ${cache.access}`;
  if (cache.family) headers["X-Family-Id"] = cache.family;
  const res = await fetch(`${API_URL}/api/v1/uploads/image`, { method: "POST", headers, body: form });
  if (!res.ok) throw new ApiError(res.status, "upload_failed", "L'envoi de la photo a échoué.");
  return (await res.json()).url;
}
