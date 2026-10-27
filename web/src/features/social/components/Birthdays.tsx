// Anniversaires des 30 prochains jours (personnes vivantes dont la date complète est connue).

import { useEffect, useState } from "react";
import { PersonLine } from "../../../components/Person";
import { api } from "../../../lib/api";
import type { Birthday } from "../../../types";

function when(b: Birthday) {
  if (b.in_days === 0) return "aujourd'hui";
  if (b.in_days === 1) return "demain";
  return new Date(b.date).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
}

export function Birthdays({ days = 30 }: { days?: number }) {
  const [items, setItems] = useState<Birthday[]>([]);
  useEffect(() => {
    void api<Birthday[]>("/birthdays", { query: { days } }).then(setItems);
  }, [days]);

  return (
    <section className="kin-group">
      <h2>Anniversaires à venir</h2>
      {items.length === 0 ? (
        <p style={{ color: "var(--muted)", margin: 0 }}>Aucun dans les {days} prochains jours.</p>
      ) : (
        <ul className="kin-list">
          {items.slice(0, 12).map((b) => (
            <li key={b.person.id}>
              <div className="kin-item">
                <PersonLine person={b.person} size={32} />
                <span className="kin-meta" style={{ textAlign: "right" }}>
                  {when(b)}
                  {b.age ? <span style={{ display: "block" }}>{b.age} ans</span> : null}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
