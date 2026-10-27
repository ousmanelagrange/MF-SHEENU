// Catalogue des titres de la famille (Mfon, Pomafon, Nji, Kom…) et leur rang de préséance.

import { App, Button, ColorPicker, Form, Input, InputNumber, Modal, Popconfirm, Space, Switch, Table } from "antd";
import { useEffect, useState } from "react";
import { PageHead } from "../../components/AppShell";
import { api } from "../../lib/api";
import type { Title } from "../../types";


export function TitlesPage() {
  const { message } = App.useApp();
  const [items, setItems] = useState<Title[]>([]);
  const [editing, setEditing] = useState<Partial<Title> | null>(null);
  const load = () => api<Title[]>("/titles").then(setItems);
  useEffect(() => {
    void load();
  }, []);

  const save = async (v: Omit<Partial<Title>, "badge_color"> & { badge_color?: unknown }) => {
    const raw = v.badge_color;
    const color =
      typeof raw === "string"
        ? raw
        : raw && typeof raw === "object" && "toHexString" in raw
          ? (raw as { toHexString: () => string }).toHexString()
          : "#9C7428";
    const body = { ...v, badge_color: color.slice(0, 7).toUpperCase() };
    try {
      if (editing?.id) await api(`/titles/${editing.id}`, { method: "PATCH", body });
      else await api("/titles", { method: "POST", body });
      message.success("Titre enregistré.");
      setEditing(null);
      void load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <PageHead
        title="Titres"
        lead="Les titres conférés par la chefferie ou le royaume. Le rang fixe l'ordre de préséance : plus il est petit, plus le titre est élevé."
        actions={
          <Button type="primary" onClick={() => setEditing({ precedence: 50, badge_color: "#9C7428" })}>
            Ajouter un titre
          </Button>
        }
      />
      <Table
        rowKey="id"
        dataSource={items}
        pagination={false}
        locale={{ emptyText: "Aucun titre. Commencez par le plus élevé, par exemple Mfon." }}
        columns={[
          { title: "Rang", dataIndex: "precedence", width: 80 },
          {
            title: "Titre",
            render: (_, t) => (
              <span>
                <span className="swatch" style={{ background: t.badge_color }} />
                <span className="pname">{t.name}</span>
                {t.abbreviation && t.abbreviation !== t.name && (
                  <span style={{ color: "var(--muted)" }}> ({t.abbreviation})</span>
                )}
              </span>
            ),
          },
          { title: "Transmissible", dataIndex: "hereditary", width: 140, render: (v) => (v ? "Oui" : "Non") },
          {
            title: "",
            width: 180,
            render: (_, t) => (
              <Space>
                <Button size="small" onClick={() => setEditing(t)}>
                  Modifier
                </Button>
                <Popconfirm
                  title="Supprimer ce titre ?"
                  description="Il sera retiré de toutes les personnes qui le portent."
                  okText="Supprimer"
                  cancelText="Annuler"
                  onConfirm={async () => {
                    await api(`/titles/${t.id}`, { method: "DELETE" });
                    void load();
                  }}
                >
                  <Button size="small" type="text" danger>
                    Supprimer
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      <Modal
        open={!!editing}
        onCancel={() => setEditing(null)}
        footer={null}
        title={editing?.id ? "Modifier le titre" : "Nouveau titre"}
        destroyOnHidden
      >
        <Form layout="vertical" requiredMark={false} initialValues={editing ?? {}} onFinish={save}>
          <Form.Item name="name" label="Nom" rules={[{ required: true }]}>
            <Input placeholder="Nji" />
          </Form.Item>
          <Form.Item name="abbreviation" label="Forme affichée devant le nom" extra="Laissez vide pour utiliser le nom.">
            <Input />
          </Form.Item>
          <div className="form-grid">
            <Form.Item name="precedence" label="Rang de préséance" rules={[{ required: true }]}>
              <InputNumber min={0} max={10000} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="badge_color" label="Couleur du badge">
              <ColorPicker disabledAlpha showText />
            </Form.Item>
          </div>
          <Form.Item name="hereditary" label="Se transmet à un successeur" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea autoSize={{ minRows: 2 }} />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            Enregistrer
          </Button>
        </Form>
      </Modal>
    </div>
  );
}
