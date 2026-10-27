// Où vit la famille : la carte, le classement des pays, et les personnes du pays choisi.

import { Spin } from "antd";
import { useEffect, useState } from "react";
import { PageHead } from "../../components/AppShell";
import { PersonLine } from "../../components/Person";
import { api } from "../../lib/api";
import { count } from "../../lib/text";
import type { PersonSummary } from "../../types";
import { isoOf } from "./countries";
import { DiasporaMap } from "./DiasporaMap";

type Diaspora = { countries: { country: string; count: number }[]; unknown: number; living: number };

export function DiasporaPage() {
  const [data, setData] = useState<Diaspora | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [people, setPeople] = useState<PersonSummary[]>([]);

  useEffect(() => void api<Diaspora>("/diaspora").then(setData), []);
  useEffect(() => {
    if (!selected) return setPeople([]);
    void api<{ items: PersonSummary[] }>("/persons", { query: { country: selected, living: true, limit: 200 } }).then((r) => setPeople(r.items));
  }, [selected]);

  if (!data) return <Spin style={{ display: "block", margin: 60 }} />;
  const located = data.living - data.unknown;
  const max = data.countries[0]?.count ?? 1;

  return (
    <div className="page">
      <PageHead
        title="La famille dans le monde"
        lead={`${count(located, "personne vivante", "personnes vivantes")} dans ${count(data.countries.length, "pays", "pays")}. ${
          data.unknown ? `Le pays de ${count(data.unknown, "autre personne", "autres personnes")} n'est pas renseigné.` : ""
        }`}
      />
      <DiasporaMap points={data.countries} selected={selected} onSelect={setSelected} />
      <div className="diaspora">
        <ol className="diaspora__ranking">
          {data.countries.map((c) => (
            <li key={c.country}>
              <button className={selected === c.country ? "is-selected" : undefined} onClick={() => setSelected(selected === c.country ? null : c.country)}>
                <span className="diaspora__name">
                  {c.country}
                  {!isoOf(c.country) && <span className="years"> (hors carte)</span>}
                </span>
                <span className="diaspora__bar" style={{ width: `${(c.count / max) * 100}%` }} />
                <span className="diaspora__count">{c.count}</span>
              </button>
            </li>
          ))}
        </ol>
        <section className="kin-group">
          <h2>{selected ? `Vivent en ${selected}` : "Choisissez un pays"}</h2>
          {selected ? (
            <ul className="kin-list">
              {people.map((p) => (
                <li key={p.id}>
                  <div className="kin-item">
                    <PersonLine person={p} size={30} />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-note" style={{ textAlign: "left", padding: 0 }}>
              Sur la carte ou dans la liste, pour voir qui y vit. Le pays se renseigne sur chaque fiche.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
