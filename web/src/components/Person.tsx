// Briques d'affichage d'une personne : portrait, badges de titres, ligne de liste, sélecteur avec recherche.

import { Select, Spin } from "antd";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { api } from "../lib/api";
import type { PersonSummary, TitleBadge } from "../types";

export function initials(p: Pick<PersonSummary, "first_name" | "last_name">) {
  return `${p.first_name?.[0] ?? ""}${p.last_name?.[0] ?? ""}`.toUpperCase();
}

export function lifeSpan(p: Pick<PersonSummary, "birth_year" | "death_year" | "is_living">) {
  if (!p.birth_year && !p.death_year) return p.is_living ? "" : "Défunt(e)";
  if (p.is_living) return p.birth_year ? `né(e) en ${p.birth_year}` : "";
  return `${p.birth_year ?? "?"} – ${p.death_year ?? "?"}`;
}

export function Avatar({ person, size = 36 }: { person: PersonSummary; size?: number }) {
  const cls = `avatar avatar--${person.sex}${person.is_living ? "" : " avatar--deceased"}`;
  return (
    <span className={cls} style={{ width: size, height: size, fontSize: size * 0.38 }}>
      {person.photo_url ? <img src={person.photo_url} alt="" /> : initials(person)}
    </span>
  );
}

export function TitleBadges({ titles, max = 2 }: { titles: TitleBadge[]; max?: number }) {
  const active = titles.filter((t) => t.active).slice(0, max);
  return (
    <>
      {active.map((t) => (
        <span
          key={t.holding_id}
          className="title-badge"
          style={{ color: t.badge_color, background: `${t.badge_color}14` }}
        >
          {t.name}
        </span>
      ))}
    </>
  );
}

export function PersonLine({
  person,
  link = true,
  size = 36,
  extra,
}: {
  person: PersonSummary;
  link?: boolean;
  size?: number;
  extra?: React.ReactNode;
}) {
  const name = <span className="pname">{person.display_name}</span>;
  return (
    <span className="person-row">
      <Avatar person={person} size={size} />
      <span className="person-row__text">
        <span className="person-row__name">
          {link ? <Link to={`/personnes/${person.id}`}>{name}</Link> : name}
          <TitleBadges titles={person.titles} />
        </span>
        <span className="years">
          {lifeSpan(person)}
          {extra}
        </span>
      </span>
    </span>
  );
}

/** Sélecteur de personne avec recherche côté serveur. */
export function PersonPicker({
  value,
  onChange,
  placeholder = "Rechercher une personne",
  exclude = [],
  style,
}: {
  value?: string | null;
  onChange?: (id: string | undefined, person?: PersonSummary) => void;
  placeholder?: string;
  exclude?: string[];
  style?: React.CSSProperties;
}) {
  const [options, setOptions] = useState<PersonSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const search = (q: string) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      setLoading(true);
      try {
        const r = await api<{ items: PersonSummary[] }>("/persons", {
          query: { q, limit: 30, sort: "name" },
        });
        setOptions(r.items);
      } finally {
        setLoading(false);
      }
    }, 220);
  };

  useEffect(() => {
    search("");
    if (value) {
      api<PersonSummary>(`/persons/${value}`).then((p) =>
        setOptions((prev) => (prev.some((o) => o.id === p.id) ? prev : [p, ...prev])),
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Select
      showSearch
      allowClear
      value={value ?? undefined}
      placeholder={placeholder}
      filterOption={false}
      onSearch={search}
      notFoundContent={loading ? <Spin size="small" /> : "Aucune personne"}
      style={{ width: "100%", ...style }}
      onChange={(id) => onChange?.(id, options.find((o) => o.id === id))}
      options={options
        .filter((o) => !exclude.includes(o.id))
        .map((p) => ({
          value: p.id,
          label: (
            <span className="person-row" style={{ gap: 8 }}>
              <Avatar person={p} size={22} />
              <span>{p.display_name}</span>
              <span className="years">{lifeSpan(p)}</span>
            </span>
          ),
        }))}
    />
  );
}
