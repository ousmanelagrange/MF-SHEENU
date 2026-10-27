// Mise en page de l'arbre, partagée avec le web (copie de web/src/features/tree/layout.ts).
// Mise en page de l'arbre : descendance (vers le bas) ou ascendance (vers le haut).
import { hierarchy, tree as d3tree, type HierarchyPointNode } from "d3-hierarchy";
import type { PersonSummary, Tree } from "./types";

export const CARD_W = 212;
export const CARD_H = 66;
export const SPOUSE_H = 22;
export const MAX_SPOUSES_SHOWN = 3;
export const GAP_X = 28;
export const GAP_Y = 64;

export type Mode = "descendants" | "ancestors";

export interface Index {
  persons: Map<string, PersonSummary>;
  children: Map<string, string[]>;
  parents: Map<string, string[]>;
  spouses: Map<string, { id: string; rank: number | null }[]>;
}

export function buildIndex(t: Tree): Index {
  const persons = new Map(t.persons.map((p) => [p.id, p]));
  const children = new Map<string, string[]>();
  const parents = new Map<string, string[]>();
  const spouses = new Map<string, { id: string; rank: number | null }[]>();
  for (const l of t.parent_child) {
    if (!persons.has(l.parent_id) || !persons.has(l.child_id)) continue;
    children.set(l.parent_id, [...(children.get(l.parent_id) ?? []), l.child_id]);
    parents.set(l.child_id, [...(parents.get(l.child_id) ?? []), l.parent_id]);
  }
  for (const u of t.unions) {
    spouses.set(u.person_a_id, [...(spouses.get(u.person_a_id) ?? []), { id: u.person_b_id, rank: u.rank }]);
    spouses.set(u.person_b_id, [...(spouses.get(u.person_b_id) ?? []), { id: u.person_a_id, rank: u.rank }]);
  }
  for (const list of spouses.values()) list.sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));
  const byBirth = (a: string, b: string) =>
    (persons.get(a)?.birth_year ?? 9999) - (persons.get(b)?.birth_year ?? 9999);
  for (const list of children.values()) list.sort(byBirth);
  for (const list of parents.values()) {
    // Père à gauche, mère à droite
    list.sort((a, b) => (persons.get(a)?.sex === "M" ? -1 : 0) - (persons.get(b)?.sex === "M" ? -1 : 0));
  }
  return { persons, children, parents, spouses };
}

export interface TNode {
  id: string;
  person: PersonSummary;
  spouses: PersonSummary[];
  hiddenCount: number; // enfants (ou parents) masqués
  children?: TNode[];
}

/** Hauteur d'une carte selon le nombre de conjoints affichés. */
export function cardHeight(n: TNode, mode: Mode) {
  if (mode === "ancestors") return CARD_H;
  return CARD_H + Math.min(n.spouses.length, MAX_SPOUSES_SHOWN) * SPOUSE_H;
}

export function buildTree(
  idx: Index,
  focusId: string,
  mode: Mode,
  depth: number,
  expanded: Set<string>,
): TNode | null {
  const seen = new Set<string>();
  const next = mode === "descendants" ? idx.children : idx.parents;

  const visit = (id: string, level: number): TNode | null => {
    const person = idx.persons.get(id);
    if (!person || seen.has(id)) return null;
    seen.add(id);
    const kids = next.get(id) ?? [];
    const open = level < depth || expanded.has(id);
    const node: TNode = {
      id,
      person,
      spouses:
        mode === "descendants"
          ? (idx.spouses.get(id) ?? []).map((s) => idx.persons.get(s.id)).filter((p): p is PersonSummary => !!p)
          : [],
      hiddenCount: open ? 0 : kids.length,
    };
    if (open && kids.length) {
      node.children = kids.map((k) => visit(k, level + 1)).filter((n): n is TNode => !!n);
    }
    return node;
  };
  return visit(focusId, 0);
}

export interface Laid {
  nodes: HierarchyPointNode<TNode>[];
  links: { source: HierarchyPointNode<TNode>; target: HierarchyPointNode<TNode> }[];
  bounds: { x0: number; y0: number; x1: number; y1: number };
  rowHeight: number;
}

export function layout(root: TNode, mode: Mode): Laid {
  const h = hierarchy(root);
  let maxH = CARD_H;
  h.each((n) => {
    maxH = Math.max(maxH, cardHeight(n.data, mode));
  });
  const rowHeight = maxH + GAP_Y;
  const laid = d3tree<TNode>()
    .nodeSize([CARD_W + GAP_X, rowHeight])
    .separation((a, b) => (a.parent === b.parent ? 1 : 1.15))(h);
  const nodes = laid.descendants();
  if (mode === "ancestors") for (const n of nodes) n.y = -n.y;
  const links = laid.links();
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const n of nodes) {
    x0 = Math.min(x0, n.x - CARD_W / 2);
    x1 = Math.max(x1, n.x + CARD_W / 2);
    y0 = Math.min(y0, n.y);
    y1 = Math.max(y1, n.y + cardHeight(n.data, mode) + (n.data.hiddenCount ? 24 : 0));
  }
  return { nodes, links, bounds: { x0, y0, x1, y1 }, rowHeight };
}
