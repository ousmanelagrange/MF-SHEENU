// Frise chronologique : l'histoire de la famille décennie par décennie, ou autour d'une personne
// (?personne=<id>). Chaque ligne mène à la fiche, au récit ou à l'album concerné.

import { Segmented, Spin } from "antd";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { PageHead } from "../../components/AppShell";
import { PersonPicker } from "../../components/Person";
import { api } from "../../lib/api";
import type { TimelineItem } from "../../types";
import { MemoryNav } from "./components/MemoryNav";

const KIND_LABEL: Record<TimelineItem["kind"], string> = {
  birth: "Naissance",
  death: "Décès",
  union: "Union",
  narrative: "Récit",
  album: "Album",
  photo: "Photo",
  life_event: "Annonce",
};

const FILTERS: Record<string, TimelineItem["kind"][] | null> = {
  all: null,
  lives: ["birth", "death", "union"],
  memory: ["narrative", "album", "photo"],
  news: ["life_event"],
};

function href(i: TimelineItem) {
  if (!i.ref_id) return null;
  if (i.kind === "narrative") return `/memoire/recits/${i.ref_id}`;
  if (i.kind === "album" || i.kind === "photo") return `/memoire/albums/${i.ref_id}`;
  if (i.kind === "life_event") return "/fil";
  return `/personnes/${i.ref_id}`;
}

export function TimelinePage() {
  const [params, setParams] = useSearchParams();
  const personId = params.get("personne");
  const [items, setItems] = useState<TimelineItem[] | null>(null);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    setItems(null);
    void api<TimelineItem[]>("/timeline", { query: { person_id: personId } }).then(setItems);
  }, [personId]);

  // Regroupement par décennie, après filtrage
  const decades = useMemo(() => {
    const kinds = FILTERS[filter];
    const groups = new Map<number, TimelineItem[]>();
    for (const i of items ?? []) {
      if (kinds && !kinds.includes(i.kind)) continue;
      const d = Math.floor(i.year / 10) * 10;
      groups.set(d, [...(groups.get(d) ?? []), i]);
    }
    return [...groups.entries()];
  }, [items, filter]);

  return (
    <div className="page" style={{ maxWidth: 920 }}>
      <PageHead title="Mémoire de la famille" lead="Les événements datés de la famille : naissances, unions, décès, récits, albums et annonces." />
      <MemoryNav />
      <div className="toolbar">
        <Segmented
          value={filter}
          onChange={(v) => setFilter(String(v))}
          options={[
            { label: "Tout", value: "all" },
            { label: "Vies", value: "lives" },
            { label: "Récits et photos", value: "memory" },
            { label: "Annonces", value: "news" },
          ]}
        />
        <PersonPicker
          value={personId}
          placeholder="Autour d'une personne"
          onChange={(id) => setParams(id ? { personne: id } : {})}
          style={{ maxWidth: 300 }}
        />
      </div>

      {!items ? (
        <Spin style={{ display: "block", margin: 40 }} />
      ) : decades.length === 0 ? (
        <p className="empty-note">Aucun événement daté. Les années de naissance, des récits et des albums nourrissent la frise.</p>
      ) : (
        <ol className="timeline">
          {decades.map(([decade, list]) => (
            <li key={decade} className="timeline__decade">
              <h2 className="timeline__year">{decade}</h2>
              <ul>
                {list.map((i, k) => {
                  const to = href(i);
                  return (
                    <li key={`${i.kind}-${i.ref_id}-${k}`} className={`timeline__item timeline__item--${i.kind}`}>
                      <span className="timeline__when">{i.year}</span>
                      <span className="timeline__kind">{KIND_LABEL[i.kind]}</span>
                      <span className="timeline__title">{to ? <Link to={to}>{i.title}</Link> : i.title}</span>
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
