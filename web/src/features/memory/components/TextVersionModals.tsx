// Proposer une version d'une couche de texte, et relire les propositions en attente.

import { App, Button, Drawer, Empty, Input, Modal } from "antd";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { LayerName, NarrativeTextVersion } from "../../../types";
import { ago } from "../../social/format";
import { diffWords, layerLabel } from "../format";

/** Proposer (ou corriger) la transcription ou une traduction. Le texte validé sert de départ. */
export function ProposeModal({
  narrativeId,
  layer,
  initial,
  curator,
  onClose,
  onSaved,
}: {
  narrativeId: string;
  layer: LayerName | null;
  initial: string;
  curator: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { message } = App.useApp();
  const [text, setText] = useState(initial);
  useEffect(() => setText(initial), [initial, layer]);

  const save = async () => {
    await api(`/narratives/${narrativeId}/texts`, { method: "POST", body: { layer, text } });
    message.success(curator ? "Texte validé." : "Proposition envoyée aux gardiens de la mémoire.");
    onSaved();
    onClose();
  };

  return (
    <Modal
      open={!!layer}
      title={layer ? `${initial ? "Corriger" : "Proposer"} : ${layerLabel(layer).toLowerCase()}` : ""}
      okText={curator ? "Valider ce texte" : "Proposer"}
      cancelText="Annuler"
      okButtonProps={{ disabled: !text.trim() || text === initial }}
      onOk={save}
      onCancel={onClose}
      width={720}
    >
      <p className="modal-note">
        {curator
          ? "Vous êtes gardien de la mémoire : votre version devient la référence. L'ancienne reste dans l'historique."
          : "Un gardien de la mémoire (bureau, secrétaire, chef de branche) relira votre proposition avant qu'elle remplace le texte."}
      </p>
      <Input.TextArea className="reading-input" value={text} onChange={(e) => setText(e.target.value)} autoSize={{ minRows: 10, maxRows: 24 }} />
    </Modal>
  );
}

/** Propositions en attente d'une couche, à valider ou refuser avec un motif. */
export function ReviewDrawer({
  narrativeId,
  layer,
  current,
  onClose,
  onDone,
}: {
  narrativeId: string;
  layer: LayerName | null;
  current: string | null; // texte validé actuel, pour montrer les changements
  onClose: () => void;
  onDone: () => void;
}) {
  const { message } = App.useApp();
  const [items, setItems] = useState<NarrativeTextVersion[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const load = () => {
    if (layer) void api<NarrativeTextVersion[]>(`/narratives/${narrativeId}/texts`, { query: { layer, status: "pending" } }).then(setItems);
  };
  useEffect(load, [narrativeId, layer]);

  const review = async (v: NarrativeTextVersion, action: "validate" | "reject") => {
    await api(`/narrative-texts/${v.id}/${action}`, { method: "POST", body: { note: notes[v.id] || null } });
    message.success(action === "validate" ? "Texte validé." : "Proposition refusée.");
    onDone();
    load();
  };

  return (
    <Drawer open={!!layer} onClose={onClose} width={640} title={layer ? `À relire : ${layerLabel(layer).toLowerCase()}` : ""}>
      {items.length === 0 ? (
        <Empty description="Plus rien à relire pour cette couche." />
      ) : (
        items.map((v) => (
          <article key={v.id} className="review-item">
            <p className="years">
              Proposé par {v.author.name}, {ago(v.created_at)}
            </p>
            {current ? (
              <>
                <p className="diff-legend">
                  Changements par rapport au texte actuel : <ins>ajouts</ins> <del>retraits</del>
                </p>
                <div className="reading">
                  {diffWords(current, v.text).map((d, k) =>
                    d.op === "add" ? <ins key={k}>{d.text}</ins> : d.op === "del" ? <del key={k}>{d.text}</del> : <span key={k}>{d.text}</span>,
                  )}
                </div>
              </>
            ) : (
              <div className="reading">{v.text}</div>
            )}
            <Input
              placeholder="Motif (facultatif, visible par l'auteur)"
              value={notes[v.id] ?? ""}
              onChange={(e) => setNotes({ ...notes, [v.id]: e.target.value })}
              style={{ margin: "12px 0" }}
            />
            <div style={{ display: "flex", gap: 8 }}>
              <Button type="primary" onClick={() => review(v, "validate")}>
                Valider
              </Button>
              <Button onClick={() => review(v, "reject")}>Refuser</Button>
            </div>
          </article>
        ))
      )}
    </Drawer>
  );
}
