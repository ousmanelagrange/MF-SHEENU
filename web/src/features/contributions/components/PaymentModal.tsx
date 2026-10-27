// Déclarer un paiement : pour soi ou pour un proche, moyen, référence, reçu,
// et pour la diaspora le montant d'origine dans sa devise.

import { App, Button, Collapse, Form, Input, InputNumber, Modal, Select, Upload } from "antd";
import type { UploadFile } from "antd";
import { useState } from "react";
import { PersonPicker } from "../../../components/Person";
import { api } from "../../../lib/api";
import { useFamily } from "../../../lib/family";
import type { ContributionEvent, Payment } from "../../../types";
import { METHOD_LABELS } from "../format";

type Values = {
  person_id: string;
  amount: number;
  method: Payment["method"];
  reference?: string;
  original_amount?: number;
  original_currency?: string;
};

export function PaymentModal({
  event,
  open,
  defaultPersonId,
  onClose,
  onDone,
}: {
  event: ContributionEvent;
  open: boolean;
  defaultPersonId?: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const { message } = App.useApp();
  const { family } = useFamily();
  const [proof, setProof] = useState<UploadFile[]>([]);
  const [saving, setSaving] = useState(false);

  const submit = async (v: Values) => {
    setSaving(true);
    try {
      const payment = await api<Payment>(`/contributions/events/${event.id}/payments`, { method: "POST", body: v });
      const file = proof[0]?.originFileObj;
      if (file) {
        const form = new FormData();
        form.append("file", file);
        await api(`/contributions/payments/${payment.id}/proof`, { method: "POST", form });
      }
      message.success(
        payment.status === "validated" ? "Paiement enregistré." : "Paiement déclaré. Le trésorier va le valider.",
      );
      setProof([]);
      onClose();
      onDone();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onCancel={onClose} footer={null} title="Déclarer un paiement" destroyOnHidden>
      <Form
        layout="vertical"
        requiredMark={false}
        onFinish={submit}
        initialValues={{ person_id: defaultPersonId ?? family?.person_id, method: "mobile_money" }}
      >
        <Form.Item name="person_id" label="Paiement pour" rules={[{ required: true }]} extra="Vous pouvez payer pour un parent ou vos enfants.">
          <PersonPicker />
        </Form.Item>
        <div className="form-grid">
          <Form.Item name="amount" label={`Montant (${event.currency === "XAF" ? "FCFA" : event.currency})`} rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} min={1} step={1000} />
          </Form.Item>
          <Form.Item name="method" label="Moyen">
            <Select options={Object.entries(METHOD_LABELS).map(([value, label]) => ({ value, label }))} />
          </Form.Item>
        </div>
        <Form.Item name="reference" label="Référence de la transaction">
          <Input placeholder="Par exemple MP261027.1532.A12345" />
        </Form.Item>
        <Form.Item label="Reçu (capture d'écran)">
          <Upload
            accept="image/*"
            maxCount={1}
            fileList={proof}
            beforeUpload={() => false}
            onChange={({ fileList }) => setProof(fileList)}
          >
            <Button>Joindre une image</Button>
          </Upload>
        </Form.Item>
        <Collapse
          ghost
          items={[
            {
              key: "diaspora",
              label: "Payé depuis l'étranger",
              children: (
                <div className="form-grid">
                  <Form.Item name="original_amount" label="Montant envoyé">
                    <InputNumber style={{ width: "100%" }} min={1} />
                  </Form.Item>
                  <Form.Item name="original_currency" label="Devise">
                    <Select allowClear options={["EUR", "USD", "GBP", "CAD"].map((c) => ({ value: c, label: c }))} />
                  </Form.Item>
                </div>
              ),
            },
          ]}
        />
        <Button type="primary" htmlType="submit" block loading={saving} style={{ marginTop: 8 }}>
          Déclarer le paiement
        </Button>
      </Form>
    </Modal>
  );
}
