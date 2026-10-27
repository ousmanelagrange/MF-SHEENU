// Relancer les retardataires (trésorier) : un message personnel par personne, avec sa part,
// ce qu'elle a versé et ce qui reste. Sans l'API WhatsApp payante, chaque message s'ouvre
// dans WhatsApp d'un clic, prêt à envoyer.

import { Button, Input, Modal, Tag } from "antd";
import { useState } from "react";
import { PersonLine } from "../../../components/Person";
import { api } from "../../../lib/api";
import type { PersonSummary } from "../../../types";

type Reminder = { person: PersonSummary; phone: string | null; text: string; status: string; link: string | null };
type Result = { backend: string; items: Reminder[] };

const STATUS: Record<string, { label: string; color?: string }> = {
  sent: { label: "Envoyé", color: "green" },
  failed: { label: "Échec de l'envoi", color: "red" },
  no_phone: { label: "Pas de numéro" },
};

export function RemindersModal({ eventId, open, onClose }: { eventId: string; open: boolean; onClose: () => void }) {
  const [note, setNote] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [opened, setOpened] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  const prepare = async () => {
    setLoading(true);
    try {
      setResult(await api<Result>(`/contributions/events/${eventId}/reminders`, { method: "POST", body: { note: note || null } }));
    } finally {
      setLoading(false);
    }
  };

  const close = () => {
    setResult(null);
    setOpened(new Set());
    onClose();
  };

  return (
    <Modal open={open} onCancel={close} footer={null} title="Relancer les retardataires" width={720} destroyOnHidden>
      {!result ? (
        <>
          <p className="modal-note">
            Chaque personne qui n'a pas tout versé reçoit un message avec sa part et ce qui reste. Ajoutez si besoin comment payer.
          </p>
          <Input.TextArea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            autoSize={{ minRows: 2 }}
            placeholder="Mobile Money du trésorier : 6 77 00 00 00 (Moussa)"
            maxLength={300}
          />
          <Button type="primary" style={{ marginTop: 16 }} loading={loading} onClick={prepare}>
            Préparer les messages
          </Button>
        </>
      ) : result.items.length === 0 ? (
        <p className="empty-note">Tout le monde est à jour.</p>
      ) : (
        <>
          <p className="modal-note">
            {result.backend === "share"
              ? `${result.items.filter((i) => i.link).length} message(s) prêt(s). Ouvrez-les un par un : WhatsApp s'ouvre avec le texte, il reste à l'envoyer.`
              : "Les messages sont partis par WhatsApp Business. En cas d'échec, ouvrez-les à la main."}
            {result.items.some((i) => !i.phone) &&
              ` ${result.items.filter((i) => !i.phone).length} personne(s) sans numéro : ajoutez-le sur leur fiche, ou celui de la personne qui les représente.`}
          </p>
          <ul className="reminders">
            {result.items.map((r) => (
              <li key={r.person.id}>
                <PersonLine person={r.person} size={28} link={false} />
                <span className="years">{r.phone ?? ""}</span>
                {STATUS[r.status] && <Tag color={STATUS[r.status].color}>{STATUS[r.status].label}</Tag>}
                {r.link && r.status !== "sent" && (
                  <Button
                    size="small"
                    type={opened.has(r.person.id) ? "default" : "primary"}
                    href={r.link}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() => setOpened(new Set(opened).add(r.person.id))}
                  >
                    {opened.has(r.person.id) ? "Rouvrir" : "Ouvrir WhatsApp"}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </Modal>
  );
}
