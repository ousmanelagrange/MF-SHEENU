// Préparation et lecture hors connexion.
//
// - prefetch() : à l'ouverture d'une famille (et à chaque retour au premier plan), on charge
//   les données de lecture utiles sans réseau : l'arbre entier, la liste des personnes, le fil,
//   la mémoire, les collectes. Elles restent sur le téléphone (cache de api.ts).
// - L'arbre (/tree) contient toutes les personnes et tous les liens : une fiche jamais ouverte
//   peut être reconstituée à partir de lui, et la recherche de personnes fonctionne hors ligne.

import { api, readCache } from "./api";
import type { PersonDetail, PersonSummary, Tree } from "./types";

export const PEOPLE_PAGE = 40;

export async function prefetch(): Promise<void> {
  const reads: [string, Record<string, string | number | undefined>?][] = [
    ["/tree"],
    ["/persons", { q: "", skip: 0, limit: PEOPLE_PAGE, sort: "precedence" }],
    ["/feed", {}],
    ["/narratives"],
    ["/albums"],
    ["/timeline"],
    ["/contributions/events"],
    ["/notifications"],
    ["/diaspora"],
  ];
  await Promise.allSettled(reads.map(([path, query]) => api(path, { query })));
  // Les collectes en cours, en détail : on doit pouvoir déclarer un paiement sans réseau
  const events = await readCache<{ id: string; status: string; can_manage: boolean }[]>("/contributions/events");
  await Promise.allSettled(
    (events ?? [])
      .filter((e) => e.status === "open")
      .flatMap((e) => [
        api(`/contributions/events/${e.id}`),
        api(`/contributions/events/${e.id}/dues`),
        ...(e.can_manage ? [api(`/contributions/events/${e.id}/payments`, { query: { status: "declared" } })] : []),
      ]),
  );
}

const byPrecedence = (a: PersonSummary, b: PersonSummary) => {
  const ta = Math.min(...a.titles.filter((t) => t.active).map((t) => t.precedence), 1e9);
  const tb = Math.min(...b.titles.filter((t) => t.active).map((t) => t.precedence), 1e9);
  return ta - tb || (a.generation ?? 99) - (b.generation ?? 99) || (a.birth_year ?? 9999) - (b.birth_year ?? 9999);
};

/** Recherche de personnes dans l'arbre gardé sur le téléphone. */
export async function searchOffline(q: string, skip: number, limit: number) {
  const tree = await readCache<Tree>("/tree");
  if (!tree) return null;
  const needle = q.trim().toLowerCase();
  const found = tree.persons
    .filter((p) => !needle || `${p.display_name} ${p.traditional_name ?? ""}`.toLowerCase().includes(needle))
    .sort(byPrecedence);
  return { items: found.slice(skip, skip + limit), total: found.length };
}

/** Fiche reconstituée depuis l'arbre : identité, parents, conjoints, enfants, fratrie.
 *  Les détails propres à la fiche (biographie, lieux, contacts) n'y figurent pas. */
export async function personOffline(id: string): Promise<PersonDetail | null> {
  const tree = await readCache<Tree>("/tree");
  const me = tree?.persons.find((p) => p.id === id);
  if (!tree || !me) return null;
  const get = (pid: string) => tree.persons.find((p) => p.id === pid);
  const parents = tree.parent_child.filter((l) => l.child_id === id);
  const children = tree.parent_child.filter((l) => l.parent_id === id);
  const parentIds = new Set(parents.map((l) => l.parent_id));
  const siblings = new Map<string, PersonSummary>();
  for (const l of tree.parent_child) {
    if (parentIds.has(l.parent_id) && l.child_id !== id) {
      const s = get(l.child_id);
      if (s) siblings.set(s.id, s);
    }
  }
  return {
    ...me,
    nickname: null,
    birth_date: null,
    birth_place: null,
    death_date: null,
    death_place: null,
    village: null,
    country: null,
    biography: null,
    phone: null,
    email: null,
    contact_visibility: "family",
    created_at: "",
    updated_at: "",
    can_edit: false,
    parents: parents.flatMap((l) =>
      get(l.parent_id) ? [{ relation_id: l.id, kind: l.kind, certainty: l.certainty, person: get(l.parent_id)! }] : [],
    ),
    children: children.flatMap((l) =>
      get(l.child_id) ? [{ relation_id: l.id, kind: l.kind, certainty: l.certainty, person: get(l.child_id)! }] : [],
    ),
    spouses: tree.unions
      .filter((u) => u.person_a_id === id || u.person_b_id === id)
      .flatMap((u) => {
        const other = get(u.person_a_id === id ? u.person_b_id : u.person_a_id);
        return other
          ? [{ union_id: u.id, kind: u.kind, rank: u.rank, start_date: null, end_date: null, end_reason: u.end_reason, person: other }]
          : [];
      }),
    siblings: [...siblings.values()].sort(byPrecedence),
  };
}
