// « Fiche gérée par » : membres à qui la fiche d'un ancien sans smartphone est confiée.
// Visible par le bureau et les chefs de branche ; le délégué peut ensuite tout compléter.

import { App, Button, Popconfirm, Select, Space } from "antd";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { Member } from "../../../types";

type Delegate = { id: string; membership_id: string; member_name: string };

export function DelegatesSection({ personId }: { personId: string }) {
  const { message } = App.useApp();
  const [delegates, setDelegates] = useState<Delegate[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [choice, setChoice] = useState<string>();

  const load = () => void api<Delegate[]>(`/persons/${personId}/delegates`).then(setDelegates);
  useEffect(() => {
    load();
    void api<Member[]>("/members").then(setMembers);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personId]);

  const add = async () => {
    try {
      await api(`/persons/${personId}/delegates`, { method: "POST", body: { membership_id: choice } });
      setChoice(undefined);
      message.success("Fiche confiée.");
      load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  const remove = async (id: string) => {
    await api(`/delegations/${id}`, { method: "DELETE" });
    load();
  };

  const taken = new Set(delegates.map((d) => d.membership_id));
  return (
    <section className="kin-group">
      <h2>Fiche gérée par</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, maxWidth: "62ch" }}>
        Pour une personne sans smartphone : le membre choisi peut compléter cette fiche et sa descendance.
      </p>
      {delegates.length > 0 && (
        <ul className="kin-list" style={{ marginBottom: 12 }}>
          {delegates.map((d) => (
            <li key={d.id} style={{ display: "flex", alignItems: "center" }}>
              <div className="kin-item" style={{ flex: 1 }}>
                <span className="pname">{d.member_name}</span>
              </div>
              <Popconfirm title="Retirer cette délégation ?" okText="Retirer" cancelText="Annuler" onConfirm={() => remove(d.id)}>
                <Button type="text" size="small" style={{ color: "var(--muted)" }}>
                  Retirer
                </Button>
              </Popconfirm>
            </li>
          ))}
        </ul>
      )}
      <Space.Compact style={{ width: "100%", maxWidth: 420 }}>
        <Select
          value={choice}
          onChange={setChoice}
          placeholder="Choisir un membre"
          style={{ flex: 1 }}
          options={members.filter((m) => !taken.has(m.id)).map((m) => ({ value: m.id, label: m.full_name }))}
        />
        <Button onClick={add} disabled={!choice}>
          Confier
        </Button>
      </Space.Compact>
    </section>
  );
}
