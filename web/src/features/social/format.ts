// Libellés et petites aides du module social.

import { api } from "../../lib/api";

export const LIFE_EVENTS: Record<string, string> = {
  birth: "Naissance",
  wedding: "Mariage",
  death: "Décès",
  success: "Réussite",
  other: "Événement",
};

export const REACTIONS: { key: string; emoji: string; label: string }[] = [
  { key: "like", emoji: "👍", label: "J'aime" },
  { key: "love", emoji: "❤️", label: "J'adore" },
  { key: "pray", emoji: "🙏", label: "Prières" },
  { key: "clap", emoji: "👏", label: "Bravo" },
];

/** « il y a 5 min », « hier », « 12 oct. ». */
export function ago(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  if (diff < 172800) return "hier";
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

/** Envoie une image et renvoie son adresse. */
export async function uploadImage(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const r = await api<{ url: string }>("/uploads/image", { method: "POST", form });
  return r.url;
}
