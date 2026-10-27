// Paiements d'une collecte : ceux à valider en premier pour le trésorier,
// les siens et les paiements validés pour un membre.

import { App, Button, Empty, Input, Modal, Space, Tag } from "antd";
import { useState } from "react";
import { PersonLine } from "../../../components/Person";
import { api } from "../../../lib/api";
import type { ContributionEvent, Payment } from "../../../types";
import { METHOD_LABELS, PAYMENT_STATUS, money } from "../format";

export function PaymentsList({
  event,
  payments,
  onChanged,
}: {
  event: ContributionEvent;
  payments: Payment[];
  onChanged: () => void;
}) {
  const { message } = App.useApp();
  const [rejecting, setRejecting] = useState<Payment | null>(null);
  const [note, setNote] = useState("");
  const editable = event.can_manage && event.status === "open";

  const validate = async (p: Payment) => {
    try {
      await api(`/contributions/payments/${p.id}/validate`, { method: "POST", body: {} });
      message.success("Paiement validé.");
      onChanged();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  const reject = async () => {
    try {
      await api(`/contributions/payments/${rejecting!.id}/reject`, { method: "POST", body: { note } });
      setRejecting(null);
      setNote("");
      onChanged();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  if (payments.length === 0) return <Empty description="Aucun paiement pour l'instant." />;
  const ordered = [...payments].sort((a, b) => Number(b.status === "declared") - Number(a.status === "declared"));

  return (
    <>
      <ul className="kin-list">
        {ordered.map((p) => (
          <li key={p.id} className="payment-row">
            <div style={{ flex: 1, minWidth: 0 }}>
              {p.person && <PersonLine person={p.person} size={32} />}
              <p className="years" style={{ margin: "4px 0 0 44px" }}>
                {METHOD_LABELS[p.method]}
                {p.reference ? `, réf. ${p.reference}` : ""}
                {p.original_amount ? `, envoyé ${p.original_amount} ${p.original_currency ?? ""}` : ""}
                {p.declared_by_name ? `, déclaré par ${p.declared_by_name}` : ""}, le{" "}
                {new Date(p.created_at).toLocaleDateString("fr-FR")}
                {p.review_note ? ` : ${p.review_note}` : ""}
              </p>
            </div>
            <Space wrap style={{ justifyContent: "flex-end" }}>
              <span className="pname">{money(p.amount, event.currency)}</span>
              {p.proof_url && (
                <a href={p.proof_url} target="_blank" rel="noreferrer">
                  Reçu
                </a>
              )}
              {editable && p.status === "declared" ? (
                <>
                  <Button size="small" type="primary" onClick={() => validate(p)}>
                    Valider
                  </Button>
                  <Button size="small" onClick={() => setRejecting(p)}>
                    Refuser
                  </Button>
                </>
              ) : (
                <Tag color={PAYMENT_STATUS[p.status].color}>{PAYMENT_STATUS[p.status].label}</Tag>
              )}
            </Space>
          </li>
        ))}
      </ul>
      <Modal
        open={!!rejecting}
        title="Refuser le paiement"
        okText="Refuser"
        cancelText="Annuler"
        okButtonProps={{ danger: true, disabled: !note.trim() }}
        onOk={reject}
        onCancel={() => setRejecting(null)}
      >
        <Input.TextArea
          autoFocus
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Motif, par exemple « transfert non reçu »"
          autoSize={{ minRows: 2 }}
        />
      </Modal>
    </>
  );
}
