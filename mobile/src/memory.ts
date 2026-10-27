// Types et libellés de la mémoire familiale, alignés sur web/src/features/memory/format.ts.

import type { Author } from "./social";
import type { PersonSummary } from "./types";

export type LayerName = "original" | "fr" | "en";

export interface NarrativeCard {
  id: string;
  title: string;
  language: string | null;
  teller: PersonSummary | null;
  media_kind: "audio" | "video" | null;
  year: number | null;
  era: string | null;
  layers: LayerName[];
  pending: number;
}

export interface TextVersion {
  id: string;
  text: string;
  author: Author;
}

export interface Narrative extends NarrativeCard {
  media_url: string | null;
  place: string | null;
  persons: PersonSummary[];
  texts: Record<LayerName, { validated: TextVersion | null; pending: number }>;
  can_review: boolean;
}

export interface AlbumCard {
  id: string;
  title: string;
  year: number | null;
  count: number;
  cover_url: string | null;
}

export interface AlbumPhoto {
  id: string;
  url: string;
  caption: string | null;
  year: number | null;
  persons: PersonSummary[];
  added_by: string;
}

export interface Album extends AlbumCard {
  description: string | null;
  photos: AlbumPhoto[];
}

export interface TimelineItem {
  year: number;
  kind: "birth" | "death" | "union" | "narrative" | "album" | "photo" | "life_event";
  title: string;
  ref_id: string | null;
}

export const LAYERS: { key: LayerName; label: string }[] = [
  { key: "original", label: "Langue d'origine" },
  { key: "fr", label: "Français" },
  { key: "en", label: "English" },
];

export const KIND_LABEL: Record<TimelineItem["kind"], string> = {
  birth: "Naissance",
  death: "Décès",
  union: "Union",
  narrative: "Récit",
  album: "Album",
  photo: "Photo",
  life_event: "Annonce",
};

/** Quand se passe le récit : année, libellé libre, ou les deux. */
export function when(n: { year: number | null; era: string | null }) {
  if (n.year && n.era) return `${n.era} (${n.year})`;
  return n.era ?? (n.year ? String(n.year) : null);
}
