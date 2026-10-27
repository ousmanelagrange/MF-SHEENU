// Libellés et petites aides du module mémoire.

import { api } from "../../lib/api";
import type { LayerName } from "../../types";

export const LAYERS: { key: LayerName; label: string; short: string }[] = [
  { key: "original", label: "Transcription", short: "Langue d'origine" },
  { key: "fr", label: "Traduction française", short: "Français" },
  { key: "en", label: "Traduction anglaise", short: "English" },
];

export const layerLabel = (key: LayerName) => LAYERS.find((l) => l.key === key)?.label ?? key;

/** Langues proposées à la saisie ; on peut en taper une autre. */
export const LANGUAGES = ["Shüpamom (bamoun)", "Fulfulde", "Ewondo", "Duala", "Bassa", "Ghomálá'", "Medumba", "Français", "Anglais", "Pidgin"];

/** Quand se passe le récit : année, libellé libre, ou les deux. */
export function when(n: { year: number | null; era: string | null }) {
  if (n.year && n.era) return `${n.era} (${n.year})`;
  return n.era ?? (n.year ? String(n.year) : null);
}

/** Envoie un enregistrement audio ou vidéo et renvoie son adresse et sa nature. */
export async function uploadMedia(file: Blob, name = "recit"): Promise<{ url: string; kind: "audio" | "video" }> {
  const form = new FormData();
  form.append("file", file, name);
  return api("/uploads/media", { method: "POST", form });
}

export type DiffPart = { text: string; op: "same" | "add" | "del" };

/** Différences mot à mot entre deux textes, paragraphe par paragraphe (les paragraphes
 *  restent courts, ce qui garde le calcul léger même pour un long récit). */
export function diffWords(before: string, after: string): DiffPart[] {
  const a = before.split(/\n{2,}/);
  const b = after.split(/\n{2,}/);
  const out: DiffPart[] = [];
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if (i > 0) out.push({ text: "\n\n", op: "same" });
    out.push(...diffParagraph(a[i] ?? "", b[i] ?? ""));
  }
  return out;
}

function diffParagraph(x: string, y: string): DiffPart[] {
  if (x === y) return [{ text: x, op: "same" }];
  const a = x.split(/(\s+)/).filter(Boolean);
  const b = y.split(/(\s+)/).filter(Boolean);
  // Plus longue sous-suite commune, table remplie depuis la fin
  const L = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--) L[i][j] = a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const parts: DiffPart[] = [];
  const push = (text: string, op: DiffPart["op"]) => {
    const last = parts[parts.length - 1];
    if (last?.op === op) last.text += text;
    else parts.push({ text, op });
  };
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) (push(a[i], "same"), i++, j++);
    else if (L[i + 1][j] >= L[i][j + 1]) push(a[i++], "del");
    else push(b[j++], "add");
  }
  while (i < a.length) push(a[i++], "del");
  while (j < b.length) push(b[j++], "add");
  return parts;
}
