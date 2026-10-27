// Listes de proches sur une fiche : parents, conjoints, enfants, fratrie.

import { Button, Popconfirm } from "antd";
import { Link } from "react-router";
import { PersonLine } from "../../../components/Person";
import type { PersonSummary } from "../../../types";

export function KinGroup({ title, empty, children }: { title: string; empty?: string; children: React.ReactNode }) {
  const isEmpty = Array.isArray(children) ? children.length === 0 : !children;
  return (
    <section className="kin-group">
      <h2>{title}</h2>
      {isEmpty && empty ? (
        <p style={{ color: "var(--muted)", margin: 0 }}>{empty}</p>
      ) : (
        <ul className="kin-list">{children}</ul>
      )}
    </section>
  );
}

/** Une ligne de proche, avec un lien vers sa fiche et, si permis, l'action « Retirer ». */
export function KinItem({
  person,
  meta,
  onRemove,
}: {
  person: PersonSummary;
  meta?: string;
  onRemove?: () => void;
}) {
  return (
    <li style={{ display: "flex", alignItems: "center" }}>
      <Link to={`/personnes/${person.id}`} style={{ flex: 1 }}>
        <PersonLine person={person} link={false} />
        <span className="kin-meta">{meta}</span>
      </Link>
      {onRemove && (
        <Popconfirm title="Retirer ce lien ?" okText="Retirer" cancelText="Annuler" onConfirm={onRemove}>
          <Button type="text" size="small" style={{ color: "var(--muted)" }}>
            Retirer
          </Button>
        </Popconfirm>
      )}
    </li>
  );
}
