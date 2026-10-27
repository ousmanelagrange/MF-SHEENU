// File d'envois hors connexion.
//
// Une action faite sans réseau (publier, commenter, réagir, voter, déclarer un paiement,
// proposer une traduction, valider une proposition…) est gardée sur le téléphone et rejouée
// dans l'ordre dès que le réseau revient. Chaque envoi porte une clé d'idempotence fixée à sa
// création : si le serveur l'a déjà reçu (réponse perdue en route), il ne l'applique pas deux fois.
//
// Au rejeu, le serveur reste l'arbitre : une action devenue impossible entre-temps (publication
// supprimée, proposition déjà traitée) est marquée « refusée » avec son motif, et l'utilisateur
// la voit dans « Envois en attente ».

import AsyncStorage from "@react-native-async-storage/async-storage";
import { Alert, AppState } from "react-native";
import { api, ApiError, isOffline, onConnectivity, ping, session, type ApiOptions } from "./api";

export type Pending = {
  id: string; // aussi la clé d'idempotence
  family: string | null;
  method: string;
  path: string;
  body?: unknown;
  label: string; // ce que voit l'utilisateur : « Commentaire : Félicitations… »
  createdAt: string;
  status: "pending" | "failed";
  error?: string;
  attempts: number;
};

const KEY = "sheenu.outbox";
let queue: Pending[] = [];
let loaded = false;
let flushing = false;
const listeners = new Set<(q: Pending[]) => void>();
const syncedListeners = new Set<() => void>();

const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}-${Math.random().toString(36).slice(2, 10)}`;

async function save() {
  await AsyncStorage.setItem(KEY, JSON.stringify(queue)).catch(() => undefined);
  listeners.forEach((l) => l([...queue]));
}

async function load() {
  if (loaded) return;
  loaded = true;
  try {
    queue = JSON.parse((await AsyncStorage.getItem(KEY)) ?? "[]");
  } catch {
    queue = [];
  }
}

/** S'abonner aux changements de la file (pour l'écran et les compteurs). */
export function onOutbox(listener: (q: Pending[]) => void) {
  listeners.add(listener);
  void load().then(() => listener([...queue]));
  return () => void listeners.delete(listener);
}

/** Prévenu quand des envois en attente viennent de passer (pour recharger un écran). */
export function onSynced(listener: () => void) {
  syncedListeners.add(listener);
  return () => void syncedListeners.delete(listener);
}

/**
 * Envoie une action ; sans réseau, la met en file d'attente.
 * Renvoie la réponse du serveur, ou `{ queued: true }` si l'envoi attend le réseau.
 */
export async function send<T>(
  path: string,
  opts: Omit<ApiOptions, "idempotencyKey" | "family"> & { label: string },
): Promise<T | { queued: true }> {
  await load();
  const id = newId();
  const item: Pending = {
    id,
    family: session.family,
    method: opts.method ?? "POST",
    path,
    body: opts.body,
    label: opts.label,
    createdAt: new Date().toISOString(),
    status: "pending",
    attempts: 0,
  };
  // Des envois plus anciens attendent : on garde l'ordre (une réponse ne passe pas avant sa question)
  if (!isOffline() && !queue.some((q) => q.status === "pending")) {
    try {
      return await api<T>(path, { method: item.method, body: item.body, idempotencyKey: id });
    } catch (e) {
      if (!(e instanceof ApiError) || e.code !== "offline") throw e; // refus du serveur : on le montre tout de suite
    }
  }
  queue.push(item);
  await save();
  return { queued: true };
}

export const isQueued = (r: unknown): r is { queued: true } => !!r && typeof r === "object" && "queued" in r;

/** Message affiché quand une action part en file d'attente. */
export function tellQueued() {
  Alert.alert(
    "Enregistré sur le téléphone",
    "Pas de réseau : ce sera envoyé automatiquement au retour de la connexion. Suivez-le dans Plus, Envois en attente.",
  );
}

/** Rejoue la file, dans l'ordre. S'arrête au premier envoi qui n'a toujours pas de réseau. */
export async function flush(): Promise<void> {
  await load();
  if (flushing || !queue.some((q) => q.status === "pending")) return;
  flushing = true;
  let sent = 0;
  try {
    for (const item of [...queue]) {
      if (item.status !== "pending") continue;
      item.attempts += 1;
      try {
        await api(item.path, { method: item.method, body: item.body, family: item.family, idempotencyKey: item.id });
        queue = queue.filter((q) => q.id !== item.id);
        sent += 1;
      } catch (e) {
        if (e instanceof ApiError && (e.code === "offline" || e.status >= 500 || e.code === "in_progress" || e.status === 429)) {
          break; // toujours pas de réseau, serveur indisponible ou débordé : on réessaiera
        }
        // Le serveur refuse (droits, publication supprimée, déjà traité…) : on garde la trace
        item.status = "failed";
        item.error = e instanceof Error ? e.message : "Envoi refusé.";
      }
      await save();
    }
  } finally {
    flushing = false;
    if (sent > 0) syncedListeners.forEach((l) => l());
  }
}

export async function retry(id: string) {
  const item = queue.find((q) => q.id === id);
  if (item) {
    item.status = "pending";
    item.error = undefined;
    await save();
    await flush();
  }
}

export async function discard(id: string) {
  queue = queue.filter((q) => q.id !== id);
  await save();
}

/**
 * Surveille la connexion : rejoue la file quand le réseau revient, quand l'application
 * repasse au premier plan, et toutes les 15 secondes tant qu'on est hors connexion.
 */
export function startSync() {
  void flush();
  const offConn = onConnectivity((off) => {
    if (!off) void flush();
  });
  const app = AppState.addEventListener("change", (state) => {
    if (state === "active")
      void ping().then((ok) => {
        if (ok) void flush();
      });
  });
  const timer = setInterval(() => {
    if (isOffline() || queue.some((q) => q.status === "pending"))
      void ping().then((ok) => {
        if (ok) void flush();
      });
  }, 15_000);
  return () => {
    offConn();
    app.remove();
    clearInterval(timer);
  };
}

/** À la déconnexion : les envois d'un compte ne doivent jamais partir avec le compte suivant. */
export async function clearOutbox() {
  queue = [];
  await AsyncStorage.removeItem(KEY).catch(() => undefined);
  listeners.forEach((l) => l([]));
}
