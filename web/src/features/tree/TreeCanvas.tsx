// Dessin SVG de l'arbre avec zoom et déplacement. Les couleurs sont en attributs pour que l'export reste autonome.

import { select } from "d3-selection";
import { zoom, zoomIdentity, type ZoomBehavior } from "d3-zoom";
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef } from "react";
import { initials, lifeSpan } from "../../components/Person";
import type { PersonSummary } from "../../types";
import {
  CARD_H,
  CARD_W,
  MAX_SPOUSES_SHOWN,
  SPOUSE_H,
  cardHeight,
  layout,
  type Mode,
  type TNode,
} from "./layout";

// Couleurs en attributs (et non en classes CSS) pour que l'export SVG/PNG/PDF soit autonome.
const C = {
  card: "#FFFFFF",
  cardMe: "#F3F4F9",
  stroke: "#DCDFE8",
  focus: "#1F2D5C",
  ink: "#141B33",
  muted: "#5D6379",
  link: "#A9B1CB",
  brass: "#9C7428",
  avatarM: "#E7EAF3",
  avatarMInk: "#1F2D5C",
  avatarF: "#EFE7EE",
  avatarFInk: "#6A3B5E",
  rule: "#EEF0F5",
};
const NAMES = "'Literata Variable', Literata, Georgia, serif";
const UI = "'Instrument Sans', system-ui, sans-serif";

export interface TreeCanvasHandle {
  fit: () => void;
  zoomBy: (k: number) => void;
  getContent: () => SVGGElement | null;
}

function clip(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function rankLabel(rank: number | null, sex: string) {
  if (!rank) return "";
  const ord = rank === 1 ? (sex === "F" ? "1re" : "1er") : `${rank}e`;
  return ` (${ord} ${sex === "F" ? "épouse" : "époux"})`;
}

function Avatar({ p, x, y, r }: { p: PersonSummary; x: number; y: number; r: number }) {
  const female = p.sex === "F";
  const id = `clip-${p.id}`;
  return (
    <g>
      <circle cx={x} cy={y} r={r} fill={female ? C.avatarF : C.avatarM} />
      {p.photo_url ? (
        <>
          <clipPath id={id}>
            <circle cx={x} cy={y} r={r} />
          </clipPath>
          <image
            href={p.photo_url}
            x={x - r}
            y={y - r}
            width={r * 2}
            height={r * 2}
            preserveAspectRatio="xMidYMid slice"
            clipPath={`url(#${id})`}
            style={p.is_living ? undefined : { filter: "grayscale(0.6)" }}
          />
        </>
      ) : (
        <text
          x={x}
          y={y + 4.5}
          textAnchor="middle"
          fontFamily={NAMES}
          fontSize={13}
          fontWeight={500}
          fill={female ? C.avatarFInk : C.avatarMInk}
        >
          {initials(p)}
        </text>
      )}
    </g>
  );
}

export const TreeCanvas = forwardRef<
  TreeCanvasHandle,
  {
    root: TNode;
    mode: Mode;
    focusId: string;
    meId: string | null;
    spouseRanks: Map<string, number | null>;
    onSelect: (id: string) => void;
    onExpand: (id: string) => void;
  }
>(function TreeCanvas({ root, mode, focusId, meId, spouseRanks, onSelect, onExpand }, ref) {
  const svgRef = useRef<SVGSVGElement>(null);
  const gRef = useRef<SVGGElement>(null);
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const laid = useMemo(() => layout(root, mode), [root, mode]);

  const fit = () => {
    const svg = svgRef.current;
    if (!svg || !zoomRef.current) return;
    const { x0, y0, x1, y1 } = laid.bounds;
    const w = svg.clientWidth;
    const h = svg.clientHeight;
    const pad = 80;
    const k = Math.min(1.1, Math.max(0.15, Math.min(w / (x1 - x0 + pad * 2), (h - 60) / (y1 - y0 + pad * 2))));
    const tx = w / 2 - ((x0 + x1) / 2) * k;
    const ty = 70 + pad * k - y0 * k;
    select(svg).call(zoomRef.current.transform, zoomIdentity.translate(tx, ty).scale(k));
  };

  useImperativeHandle(ref, () => ({
    fit,
    zoomBy: (k: number) => {
      if (svgRef.current && zoomRef.current) select(svgRef.current).call(zoomRef.current.scaleBy, k);
    },
    getContent: () => gRef.current,
  }));

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const z = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.08, 2.5])
      .on("zoom", (e) => gRef.current?.setAttribute("transform", e.transform.toString()));
    zoomRef.current = z;
    select(svg).call(z).on("dblclick.zoom", null);
  }, []);

  /** Vue d'ouverture : tout l'arbre s'il reste lisible, sinon la personne centrale à taille normale. */
  const initialView = () => {
    const svg = svgRef.current;
    if (!svg || !zoomRef.current) return;
    const { x0, y0, x1, y1 } = laid.bounds;
    const w = svg.clientWidth;
    const h = svg.clientHeight;
    const fitK = Math.min(w / (x1 - x0 + 160), (h - 60) / (y1 - y0 + 160));
    if (fitK >= 0.6) return fit();
    const node = laid.nodes.find((n) => n.data.id === focusId) ?? laid.nodes[0];
    const k = 1;
    const tx = w / 2 - node.x * k;
    const ty = mode === "descendants" ? 96 - node.y * k : h - 110 - (node.y + CARD_H) * k;
    select(svg).call(zoomRef.current.transform, zoomIdentity.translate(tx, ty).scale(k));
  };

  useEffect(() => {
    initialView();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId, mode, root.id]);

  const elbow = (sx: number, sy: number, tx: number, ty: number) => {
    const my = (sy + ty) / 2;
    return `M${sx},${sy}V${my}H${tx}V${ty}`;
  };

  return (
    <svg ref={svgRef} className="tree-svg" role="img" aria-label="Arbre généalogique">
      <g ref={gRef}>
        <g>
          {laid.links.map(({ source, target }) => {
            const d =
              mode === "descendants"
                ? elbow(source.x, source.y + cardHeight(source.data, mode), target.x, target.y)
                : elbow(source.x, source.y, target.x, target.y + CARD_H);
            return <path key={`${source.data.id}-${target.data.id}`} d={d} fill="none" stroke={C.link} strokeWidth={1.3} />;
          })}
        </g>
        {laid.nodes.map((n) => {
          const p = n.data.person;
          const h = cardHeight(n.data, mode);
          const x = n.x - CARD_W / 2;
          const y = n.y;
          const isFocus = p.id === focusId;
          const isMe = p.id === meId;
          const title = p.titles.find((t) => t.active);
          const name = clip(p.display_name, 19);
          const sub = [lifeSpan(p), p.generation ? `génération ${p.generation}` : ""]
            .filter(Boolean)
            .join(", ");
          return (
            <g key={p.id} className="tnode" onClick={() => onSelect(p.id)}>
              <title>{p.display_name}</title>
              <rect
                x={x}
                y={y}
                width={CARD_W}
                height={h}
                rx={8}
                fill={isMe ? C.cardMe : C.card}
                stroke={isFocus ? C.focus : C.stroke}
                strokeWidth={isFocus ? 2 : 1}
              />
              {title && <rect x={x} y={y + 10} width={3} height={CARD_H - 20} rx={1.5} fill={title.badge_color} />}
              <Avatar p={p} x={x + 32} y={y + CARD_H / 2} r={19} />
              <text x={x + 60} y={y + 27} fontFamily={NAMES} fontSize={13.5} fontWeight={500} fill={C.ink}>
                {name}
              </text>
              <text x={x + 60} y={y + 45} fontFamily={UI} fontSize={11.5} fill={C.muted}>
                {clip(sub, 30)}
              </text>
              {title && (
                <text x={x + 60} y={y + 58} fontFamily={UI} fontSize={10.5} fontWeight={600} fill={title.badge_color}>
                  {title.name}
                </text>
              )}
              {mode === "descendants" &&
                n.data.spouses.slice(0, MAX_SPOUSES_SHOWN).map((s, i) => (
                  <g key={s.id} onClick={(e) => (e.stopPropagation(), onSelect(s.id))}>
                    <line
                      x1={x + 12}
                      x2={x + CARD_W - 12}
                      y1={y + CARD_H + i * SPOUSE_H}
                      y2={y + CARD_H + i * SPOUSE_H}
                      stroke={C.rule}
                    />
                    <text x={x + 14} y={y + CARD_H + i * SPOUSE_H + 15} fontFamily={UI} fontSize={11.5} fill={C.muted}>
                      <tspan fill={C.brass}>∞ </tspan>
                      <tspan fill={C.ink}>{clip(s.display_name, 18)}</tspan>
                      {rankLabel(spouseRanks.get(`${p.id}:${s.id}`) ?? null, s.sex)}
                    </text>
                  </g>
                ))}
              {mode === "descendants" && n.data.spouses.length > MAX_SPOUSES_SHOWN && (
                <text x={x + CARD_W - 12} y={y + 15} textAnchor="end" fontFamily={UI} fontSize={10.5} fill={C.muted}>
                  +{n.data.spouses.length - MAX_SPOUSES_SHOWN} conjoints
                </text>
              )}
              {n.data.hiddenCount > 0 && (
                <g
                  className="texpand"
                  onClick={(e) => {
                    e.stopPropagation();
                    onExpand(p.id);
                  }}
                >
                  <title>{mode === "descendants" ? "Afficher les enfants" : "Afficher les parents"}</title>
                  {mode === "descendants" ? (
                    <>
                      <line x1={n.x} x2={n.x} y1={y + h} y2={y + h + 10} stroke={C.link} />
                      <rect x={n.x - 22} y={y + h + 10} width={44} height={20} rx={10} fill="#fff" stroke={C.link} />
                      <text x={n.x} y={y + h + 24} textAnchor="middle" fontFamily={UI} fontSize={11} fontWeight={600} fill={C.focus}>
                        +{n.data.hiddenCount}
                      </text>
                    </>
                  ) : (
                    <>
                      <line x1={n.x} x2={n.x} y1={y} y2={y - 10} stroke={C.link} />
                      <rect x={n.x - 22} y={y - 30} width={44} height={20} rx={10} fill="#fff" stroke={C.link} />
                      <text x={n.x} y={y - 16} textAnchor="middle" fontFamily={UI} fontSize={11} fontWeight={600} fill={C.focus}>
                        +{n.data.hiddenCount}
                      </text>
                    </>
                  )}
                </g>
              )}
            </g>
          );
        })}
      </g>
    </svg>
  );
});
