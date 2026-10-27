// Ajuster le montant dû d'une personne ou l'exempter, avec une note (trésorier).

import { App, Button, Checkbox, Form, Input, InputNumber, Modal } from "antd";
import { api } from "../../../lib/api";
import type { DueRow } from "../../../types";

export function DueEditModal({ row, onClose, onDone }: { row: DueRow | null; onClose: () => void; onDone: () => void }) {
  const { message } = App.useApp();
  const submit = async (v: { amount: number; exempt: boolean; note?: string }) => {
    try {
      await api(`/contributions/dues/${row!.due_id}`, { method: "PATCH", body: v });
      message.success("Montant mis à jour.");
      onClose();
      onDone();
    } catch (e) {
      message.error((e as Error).message);
    }
  };
  return (
    <Modal open={!!row} onCancel={onClose} footer={null} title={`Montant dû par ${row?.person.display_name ?? ""}`} destroyOnHidden>
      {row && (
        <Form layout="vertical" requiredMark={false} onFinish={submit} initialValues={{ amount: row.amount, exempt: row.exempt, note: row.note }}>
          <Form.Item name="amount" label="Montant dû">
            <InputNumber style={{ width: "100%" }} min={0} step={1000} />
          </Form.Item>
          <Form.Item name="exempt" valuePropName="checked">
            <Checkbox>Exempter cette personne</Checkbox>
          </Form.Item>
          <Form.Item name="note" label="Note" extra="Visible par la famille, par exemple « étudiant » ou « malade ».">
            <Input maxLength={300} />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            Enregistrer
          </Button>
        </Form>
      )}
    </Modal>
  );
}
