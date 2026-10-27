// Client HTTP mobile : jetons conservés sur l'appareil, rafraîchissement automatique, famille courante.

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
    await AsyncStorage.multiRemove([K.access, K.refresh, K.family]);
  },
};

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function refresh(): Promise<boolean> {
  if (!cache.refresh) return false;
  const r = await fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: cache.refresh }),
  });
  if (!r.ok) return false;
  const t = await r.json();
  await session.setTokens(t.access_token, t.refresh_token);
  return true;
}

export async function api<T>(
  path: string,
  opts: { method?: string; body?: unknown; query?: Record<string, string | number | undefined> } = {},
): Promise<T> {
  const qs = Object.entries(opts.query ?? {})
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");
  const url = `${API_URL}/api/v1${path}${qs ? `?${qs}` : ""}`;
  const send = () => {
    const headers: Record<string, string> = {};
    if (cache.access) headers.Authorization = `Bearer ${cache.access}`;
    if (cache.family) headers["X-Family-Id"] = cache.family;
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    return fetch(url, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  };
  let res = await send();
  if (res.status === 401 && (await refresh())) res = await send();
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
  return res.json();
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
