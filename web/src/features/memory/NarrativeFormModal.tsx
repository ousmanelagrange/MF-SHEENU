// Nouveau récit : qui raconte, de quoi, quand ; l'enregistrement et, si on l'a, le texte.

import { App, AutoComplete, Form, Input, InputNumber, Modal } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router";
import { PersonPicker } from "../../components/Person";
import { api } from "../../lib/api";
import type { Narrative, PersonSummary } from "../../types";
import { PersonsField } from "./components/PersonsField";
import { Recorder, type PickedMedia } from "./components/Recorder";
import { LANGUAGES, uploadMedia } from "./format";

type Values = {
  title: string;
  language?: string;
  teller_id?: string;
  year?: number;
  era?: string;
  place?: string;
  persons?: PersonSummary[];
  transcript?: string;
};

export function NarrativeFormModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [form] = Form.useForm<Values>();
  const [media, setMedia] = useState<PickedMedia | null>(null);
  const [saving, setSaving] = useState(false);

  const save = async (v: Values) => {
    setSaving(true);
    try {
      const uploaded = media ? await uploadMedia(media.blob, media.name) : null;
      const n = await api<Narrative>("/narratives", {
        method: "POST",
        body: {
          title: v.title,
          language: v.language || null,
          teller_id: v.teller_id ?? null,
          year: v.year ?? null,
          era: v.era || null,
          place: v.place || null,
          person_ids: (v.persons ?? []).map((p) => p.id),
          media_url: uploaded?.url ?? null,
          media_kind: uploaded?.kind ?? null,
          transcript: v.transcript || null,
        },
      });
      message.success("Récit enregistré.");
      onClose();
      navigate(`/memoire/recits/${n.id}`);
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      title="Nouveau récit"
      okText="Enregistrer le récit"
      cancelText="Annuler"
      onOk={() => form.submit()}
      onCancel={onClose}
      confirmLoading={saving}
      width={620}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={save} requiredMark={false}>
        <Form.Item name="title" label="Titre" rules={[{ required: true, min: 2, message: "Donnez un titre au récit." }]}>
          <Input placeholder="L'arrivée de la reine à Foumban" />
        </Form.Item>
        <Form.Item label="Enregistrement">
          <Recorder value={media} onChange={setMedia} />
        </Form.Item>
        <div className="form-row">
          <Form.Item name="teller_id" label="Qui raconte" style={{ flex: 1 }}>
            <PersonPicker placeholder="Le conteur ou la conteuse" />
          </Form.Item>
          <Form.Item name="language" label="Langue" style={{ flex: 1 }}>
            <AutoComplete options={LANGUAGES.map((l) => ({ value: l }))} placeholder="Shüpamom (bamoun)" filterOption />
          </Form.Item>
        </div>
        <div className="form-row">
          <Form.Item name="era" label="Époque" style={{ flex: 2 }}>
            <Input placeholder="Sous le règne du roi Njoya" />
          </Form.Item>
          <Form.Item name="year" label="Année approximative" style={{ flex: 1 }}>
            <InputNumber min={1000} max={2100} style={{ width: "100%" }} />
          </Form.Item>
        </div>
        <Form.Item name="place" label="Lieu">
          <Input placeholder="Foumban" />
        </Form.Item>
        <Form.Item name="persons" label="Personnes dont parle le récit">
          <PersonsField />
        </Form.Item>
        <Form.Item
          name="transcript"
          label="Texte dans la langue du récit"
          extra="Facultatif. On peut l'ajouter plus tard ; la famille propose aussi les traductions."
        >
          <Input.TextArea autoSize={{ minRows: 3, maxRows: 10 }} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
