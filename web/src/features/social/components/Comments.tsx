// Commentaires d'une publication : lecture, ajout, suppression (auteur ou modération).

import { Button, Input, Spin } from "antd";
import { useEffect, useState } from "react";
import { Avatar } from "../../../components/Person";
import { api } from "../../../lib/api";
import type { CommentItem } from "../../../types";
import { ago } from "../format";

export function Comments({ postId, onCount }: { postId: string; onCount: (n: number) => void }) {
  const [items, setItems] = useState<CommentItem[] | null>(null);
  const [text, setText] = useState("");

  useEffect(() => {
    void api<CommentItem[]>(`/posts/${postId}/comments`).then(setItems);
  }, [postId]);

  const update = (next: CommentItem[]) => {
    setItems(next);
    onCount(next.length);
  };

  const send = async () => {
    const c = await api<CommentItem>(`/posts/${postId}/comments`, { method: "POST", body: { text } });
    setText("");
    update([...(items ?? []), c]);
  };

  if (!items) return <Spin size="small" style={{ margin: 12 }} />;
  return (
    <div className="comments">
      {items.map((c) => (
        <div key={c.id} className="comment">
          {c.author.person && <Avatar person={c.author.person} size={28} />}
          <div style={{ flex: 1 }}>
            <span className="pname" style={{ fontSize: 14 }}>
              {c.author.name}
            </span>{" "}
            <span className="years">{ago(c.created_at)}</span>
            <p style={{ margin: "2px 0 0", whiteSpace: "pre-wrap" }}>{c.text}</p>
          </div>
          {c.can_delete && (
            <Button
              type="text"
              size="small"
              style={{ color: "var(--muted)" }}
              onClick={async () => {
                await api(`/comments/${c.id}`, { method: "DELETE" });
                update(items.filter((x) => x.id !== c.id));
              }}
            >
              Supprimer
            </Button>
          )}
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onPressEnter={() => text.trim() && send()}
          placeholder="Écrire un commentaire"
        />
        <Button onClick={send} disabled={!text.trim()}>
          Envoyer
        </Button>
      </div>
    </div>
  );
}
