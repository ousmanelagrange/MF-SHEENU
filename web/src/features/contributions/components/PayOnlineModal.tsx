// Payer sa part par Mobile Money, quand la famille a branché un prestataire de paiement.
// Le paiement est confirmé par le prestataire : le trésorier n'a rien à valider.

import { Alert, Button, Form, Input, InputNumber, Modal } from "antd";
import { useState } from "react";
import { PersonPicker } from "../../../components/Person";
import { api } from "../../../lib/api";
import { useFamily } from "../../../lib/family";
import type { ContributionEvent } from "../../../types";

type Started = { reference: string; instructions: string };

export function PayOnlineModal({ event, open, onClose, onDone }: { event: ContributionEvent; open: boolean; onClose: () => void; onDone: () => void }) {
  const { family } = useFamily();
  const [started, setStarted] = useState<Started | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = async (v: { person_id: string; amount: number; phone: string }) => {
    setError(null);
    try {
      setStarted(await api<Started>(`/contributions/events/${event.id}/pay-online`, { method: "POST", body: v }));
      onDone();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const close = () => {
    setStarted(null);
    onClose();
  };

  return (
    <Modal open={open} title="Payer par Mobile Money" footer={null} onCancel={close} destroyOnHidden>
      {started ? (
        <>
          <Alert type="info" showIcon message={started.instructions} description={`Référence : ${started.reference}`} />
          <p className="modal-note" style={{ marginTop: 16 }}>
            Le paiement apparaîtra comme validé dès la confirmation de l'opérateur.
          </p>
          <Button onClick={close}>Fermer</Button>
        </>
      ) : (
        <Form layout="vertical" requiredMark={false} onFinish={start} initialValues={{ person_id: family?.person_id }}>
          {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
          <Form.Item name="person_id" label="Pour" rules={[{ required: true }]}>
            <PersonPicker />
          </Form.Item>
          <Form.Item name="amount" label={`Montant (${event.currency === "XAF" ? "FCFA" : event.currency})`} rules={[{ required: true }]}>
            <InputNumber min={100} step={500} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="phone" label="Numéro Mobile Money" rules={[{ required: true, min: 6 }]}>
            <Input placeholder="6 77 12 34 56" inputMode="tel" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            Lancer le paiement
          </Button>
        </Form>
      )}
    </Modal>
  );
}
