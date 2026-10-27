// Types et libellés du fil de la famille, alignés sur web/src/features/social/format.ts.

import type { PersonSummary } from "./types";

export interface Author {
  user_id: string;
  name: string;
  person: PersonSummary | null;
}

export interface Post {
  id: string;
  kind: "post" | "announcement" | "life_event" | "poll";
  life_event: "birth" | "wedding" | "death" | "success" | "other" | null;
  text: string;
  media: string[];
  author: Author;
  pinned: boolean;
  created_at: string;
  reactions: Record<string, number>;
  my_reaction: string | null;
  comments_count: number;
  poll: { id: string; label: string; votes: number }[] | null;
  my_vote: string | null;
  can_edit: boolean;
  can_moderate: boolean;
}

export interface CommentItem {
  id: string;
  author: Author;
  text: string;
  created_at: string;
  can_delete: boolean;
}

export interface StoryGroup {
  author: Author;
  stories: { id: string; media_url: string; caption: string | null; created_at: string }[];
}

export const LIFE_EVENTS: Record<string, string> = {
  birth: "Naissance",
  wedding: "Mariage",
  death: "Décès",
  success: "Réussite",
  other: "Événement",
};

export const REACTIONS = [
  { key: "like", emoji: "👍" },
  { key: "love", emoji: "❤️" },
  { key: "pray", emoji: "🙏" },
  { key: "clap", emoji: "👏" },
];

/** Étiquette affichée au-dessus d'une publication qui n'est pas un simple message. */
export function kindLabel(p: Post) {
  if (p.kind === "announcement") return "Annonce du bureau";
  if (p.kind === "life_event") return LIFE_EVENTS[p.life_event ?? "other"];
  if (p.kind === "poll") return "Sondage";
  return null;
}

/** « à l'instant », « il y a 5 min », « hier », « 12 oct. ». */
export function ago(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  if (diff < 172800) return "hier";
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

/** Met à jour localement les compteurs après un appui sur une réaction. */
export function toggleReaction(p: Post, key: string): Post {
  const removing = p.my_reaction === key;
  const reactions = { ...p.reactions };
  if (p.my_reaction) reactions[p.my_reaction] = Math.max(0, (reactions[p.my_reaction] ?? 1) - 1);
  if (!removing) reactions[key] = (reactions[key] ?? 0) + 1;
  return { ...p, reactions, my_reaction: removing ? null : key };
}
