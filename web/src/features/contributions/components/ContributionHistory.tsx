// Historique des cotisations d'une personne : chaque collecte, son dû et ce qu'elle a payé.
// Affiché sur la fiche et, pour soi-même, sur l'accueil.

import { Tag } from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../lib/api";
import type { PersonContribution } from "../../../types";
import { STATUS_COLORS, STATUS_LABELS, money } from "../format";

export function ContributionHistory({
  personId,
  title = "Cotisations",
  onlyOpen = false,
}: {
  personId: string;
  title?: string;
  onlyOpen?: boolean;
}) {
  const [items, setItems] = useState<PersonContribution[]>([]);

  useEffect(() => {
    void api<PersonContribution[]>(`/contributions/persons/${personId}`)
      .then((all) => setItems(onlyOpen ? all.filter((i) => i.event.status === "open") : all))
      .catch(() => setItems([]));
  }, [personId, onlyOpen]);

  if (items.length === 0) return null;
  return (
    <section className="kin-group">
      <h2>{title}</h2>
      <ul className="kin-list">
        {items.map((i) => (
          <li key={i.event.id}>
            <Link to={`/cotisations/${i.event.id}`} className="kin-item">
              <span>
                <span className="pname">{i.event.title}</span>
                <span className="years" style={{ display: "block" }}>
                  {i.amount
                    ? `${money(i.paid, i.event.currency)} payés sur ${money(i.amount, i.event.currency)}`
                    : `${money(i.paid, i.event.currency)} versés`}
                </span>
              </span>
              <Tag color={STATUS_COLORS[i.status]}>{STATUS_LABELS[i.status]}</Tag>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
