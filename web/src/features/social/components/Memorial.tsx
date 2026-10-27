// Mémorial sur la fiche d'une personne décédée : hommages et condoléances de la famille.

import { Button, Input } from "antd";
import { useEffect, useState } from "react";
import { Avatar } from "../../../components/Person";
import { api } from "../../../lib/api";
import type { Author } from "../../../types";
import { ago } from "../format";

type Tribute = { id: string; author: Author; text: string; created_at: string; can_delete: boolean };

export function Memorial({ personId, firstName }: { personId: string; firstName: string }) {
  const [items, setItems] = useState<Tribute[]>([]);
  const [text, setText] = useState("");

  useEffect(() => {
    void api<Tribute[]>(`/persons/${personId}/memorial`).then(setItems);
  }, [personId]);

  const send = async () => {
    const t = await api<Tribute>(`/persons/${personId}/memorial`, { method: "POST", body: { text } });
    setItems([t, ...items]);
    setText("");
  };

  return (
    <section className="kin-group memorial">
      <h2>En mémoire de {firstName}</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Input.TextArea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Un souvenir, un hommage, une prière…"
          autoSize={{ minRows: 1, maxRows: 6 }}
        />
        <Button onClick={send} disabled={!text.trim()}>
          Déposer
        </Button>
      </div>
      {items.map((t) => (
        <div key={t.id} className="comment">
          {t.author.person && <Avatar person={t.author.person} size={28} />}
          <div style={{ flex: 1 }}>
            <span className="pname" style={{ fontSize: 14 }}>
              {t.author.name}
            </span>{" "}
            <span className="years">{ago(t.created_at)}</span>
            <p style={{ margin: "2px 0 0", whiteSpace: "pre-wrap" }}>{t.text}</p>
          </div>
          {t.can_delete && (
            <Button
              type="text"
              size="small"
              style={{ color: "var(--muted)" }}
              onClick={async () => {
                await api(`/memorial/${t.id}`, { method: "DELETE" });
                setItems(items.filter((x) => x.id !== t.id));
              }}
            >
              Retirer
            </Button>
          )}
        </div>
      ))}
    </section>
  );
}
