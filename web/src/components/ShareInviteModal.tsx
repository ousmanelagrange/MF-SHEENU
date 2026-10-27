// Fenêtre de partage d'un lien d'invitation : WhatsApp en un clic, ou copie du message.

import { App, Button, Input, Modal, Space } from "antd";

export function ShareInviteModal({
  title,
  shareText,
  onClose,
}: {
  title: string;
  shareText: string | null;
  onClose: () => void;
}) {
  const { message } = App.useApp();
  return (
    <Modal open={!!shareText} onCancel={onClose} footer={null} title={title}>
      {shareText && (
        <>
          <p style={{ color: "var(--muted)", marginTop: 0 }}>
            Ce lien est personnel, valable 7 jours et utilisable une seule fois.
          </p>
          <Input.TextArea value={shareText} autoSize readOnly />
          <Space style={{ marginTop: 16 }} wrap>
            <Button
              type="primary"
              href={`https://wa.me/?text=${encodeURIComponent(shareText)}`}
              target="_blank"
              rel="noreferrer"
            >
              Partager sur WhatsApp
            </Button>
            <Button
              onClick={() => {
                void navigator.clipboard.writeText(shareText);
                message.success("Message copié.");
              }}
            >
              Copier le message
            </Button>
          </Space>
        </>
      )}
    </Modal>
  );
}
