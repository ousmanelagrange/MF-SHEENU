// Récapitulatif de la collecte, prêt à coller dans le groupe WhatsApp de la famille.

import { App, Button, Input, Modal, Segmented, Space } from "antd";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

export function RecapModal({ eventId, open, onClose }: { eventId: string; open: boolean; onClose: () => void }) {
  const { message } = App.useApp();
  const [onlyUnpaid, setOnlyUnpaid] = useState(false);
  const [text, setText] = useState("");

  useEffect(() => {
    if (!open) return;
    void api<{ text: string }>(`/contributions/events/${eventId}/recap`, { query: { only_unpaid: onlyUnpaid } }).then(
      (r) => setText(r.text),
    );
  }, [open, eventId, onlyUnpaid]);

  return (
    <Modal open={open} onCancel={onClose} footer={null} title="Récapitulatif pour WhatsApp" width={620}>
      <Segmented
        value={onlyUnpaid ? "unpaid" : "all"}
        onChange={(v) => setOnlyUnpaid(v === "unpaid")}
        options={[
          { label: "Toute la liste", value: "all" },
          { label: "Reste à régler", value: "unpaid" },
        ]}
        style={{ marginBottom: 12 }}
      />
      <Input.TextArea value={text} readOnly autoSize={{ minRows: 8, maxRows: 18 }} style={{ fontSize: 14 }} />
      <Space style={{ marginTop: 16 }} wrap>
        <Button type="primary" href={`https://wa.me/?text=${encodeURIComponent(text)}`} target="_blank" rel="noreferrer">
          Partager sur WhatsApp
        </Button>
        <Button
          onClick={() => {
            void navigator.clipboard.writeText(text);
            message.success("Récapitulatif copié.");
          }}
        >
          Copier
        </Button>
      </Space>
    </Modal>
  );
}
