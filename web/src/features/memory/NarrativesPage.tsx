// Récits de la famille : liste, recherche, récits à relire, et création d'un récit.

import { AudioOutlined, PlusOutlined, VideoCameraOutlined } from "@ant-design/icons";
import { Button, Checkbox, Empty, Input, Spin } from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { PageHead } from "../../components/AppShell";
import { Avatar } from "../../components/Person";
import { api } from "../../lib/api";
import { useFamily } from "../../lib/family";
import type { NarrativeCard } from "../../types";
import { MemoryNav } from "./components/MemoryNav";
import { LAYERS, when } from "./format";
import { NarrativeFormModal } from "./NarrativeFormModal";

const CURATORS = ["admin", "secretary", "branch_head"];

export function NarrativesPage() {
  const { family } = useFamily();
  const [items, setItems] = useState<NarrativeCard[] | null>(null);
  const [q, setQ] = useState("");
  const [toReview, setToReview] = useState(false);
  const [creating, setCreating] = useState(false);
  const curator = CURATORS.includes(family?.role ?? "");

  useEffect(() => {
    const t = window.setTimeout(() => {
      void api<NarrativeCard[]>("/narratives", { query: { q, to_review: toReview || undefined } }).then(setItems);
    }, 200);
    return () => window.clearTimeout(t);
  }, [q, toReview]);

  return (
    <div className="page" style={{ maxWidth: 920 }}>
      <PageHead
        title="Mémoire de la famille"
        lead="Les histoires racontées par les anciens, dans leur langue, avec leur transcription et leurs traductions relues par la famille."
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>
            Nouveau récit
          </Button>
        }
      />
      <MemoryNav />
      <div className="toolbar">
        <Input.Search placeholder="Rechercher un récit" allowClear value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 320 }} />
        {curator && (
          <Checkbox checked={toReview} onChange={(e) => setToReview(e.target.checked)}>
            Avec des textes à relire
          </Checkbox>
        )}
      </div>

      {!items ? (
        <Spin style={{ display: "block", margin: 40 }} />
      ) : items.length === 0 ? (
        <Empty description={q || toReview ? "Aucun récit ne correspond." : "Aucun récit pour l'instant. Enregistrez la première histoire d'un ancien."} />
      ) : (
        <ul className="narratives">
          {items.map((n) => (
            <li key={n.id}>
              <Link to={`/memoire/recits/${n.id}`} className="narrative-row">
                <span className="narrative-row__media" aria-label={n.media_kind ?? "texte"}>
                  {n.media_kind === "video" ? <VideoCameraOutlined /> : n.media_kind === "audio" ? <AudioOutlined /> : null}
                </span>
                <span className="narrative-row__main">
                  <span className="narrative-row__title">{n.title}</span>
                  <span className="narrative-row__meta">
                    {n.teller && (
                      <span className="narrative-row__teller">
                        <Avatar person={n.teller} size={20} /> {n.teller.display_name}
                      </span>
                    )}
                    {when(n) && <span>{when(n)}</span>}
                    {n.language && <span>{n.language}</span>}
                  </span>
                </span>
                <span className="narrative-row__layers">
                  {LAYERS.map((l) => (
                    <span key={l.key} className={`layer-tag${n.layers.includes(l.key) ? " is-on" : ""}`} title={l.label}>
                      {l.key === "original" ? "Texte" : l.key.toUpperCase()}
                    </span>
                  ))}
                  {curator && n.pending > 0 && <span className="pending-note">{n.pending} à relire</span>}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <NarrativeFormModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}
