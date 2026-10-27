// Attribuer un titre à une personne (administrateur) : titre, autorité qui l'a conféré, date.

import { App, Button, DatePicker, Form, Input, Modal, Select } from "antd";
import type { Dayjs } from "dayjs";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../lib/api";
import type { Title } from "../../../types";

type Values = { title_id: string; conferred_by?: string; conferred_on?: Dayjs };

export function GrantTitleModal({
  open,
  personId,
  onClose,
  onDone,
}: {
  open: boolean;
  personId: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const { message } = App.useApp();
  const [titles, setTitles] = useState<Title[]>([]);

  useEffect(() => {
    if (open) void api<Title[]>("/titles").then(setTitles);
  }, [open]);

  const submit = async (v: Values) => {
    try {
      await api(`/persons/${personId}/titles`, {
        method: "POST",
        body: { ...v, conferred_on: v.conferred_on?.format("YYYY-MM-DD") },
      });
      message.success("Titre attribué.");
      onClose();
      onDone();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  return (
    <Modal open={open} onCancel={onClose} footer={null} title="Attribuer un titre" destroyOnHidden>
      {titles.length === 0 ? (
        <p>
          Aucun titre n'est encore défini. <Link to="/titres">Créer les titres de la famille</Link>
        </p>
      ) : (
        <Form layout="vertical" requiredMark={false} onFinish={submit}>
          <Form.Item name="title_id" label="Titre" rules={[{ required: true }]}>
            <Select options={titles.map((t) => ({ value: t.id, label: t.name }))} />
          </Form.Item>
          <Form.Item name="conferred_by" label="Conféré par" extra="Chefferie, palais royal, autorité traditionnelle">
            <Input />
          </Form.Item>
          <Form.Item name="conferred_on" label="Date">
            <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            Attribuer
          </Button>
        </Form>
      )}
    </Modal>
  );
}
