// Barèmes de cotisation : la transcription des textes de l'association
// (montant par génération, exemptions). Réservé au trésorier et au bureau.

import { MinusCircleOutlined } from "@ant-design/icons";
import { App, Button, Checkbox, Form, Input, InputNumber, Modal, Select, Space, Spin, Switch, Table } from "antd";
import { useEffect, useState } from "react";
import { PageHead } from "../../components/AppShell";
import { api } from "../../lib/api";
import type { Scale } from "../../types";
import { money } from "./format";

type Line = { generation: number; amount: number };
type Values = Omit<Scale, "id" | "amounts_by_generation" | "active"> & { lines: Line[] };

const toLines = (s?: Partial<Scale>): Line[] =>
  Object.entries(s?.amounts_by_generation ?? {})
    .map(([g, amount]) => ({ generation: Number(g), amount }))
    .sort((a, b) => a.generation - b.generation);

export function ScalesPage() {
  const { message } = App.useApp();
  const [scales, setScales] = useState<Scale[] | null>(null);
  const [editing, setEditing] = useState<Partial<Scale> | null>(null);

  const load = () => void api<Scale[]>("/contributions/scales").then(setScales);
  useEffect(load, []);

  const save = async ({ lines, ...v }: Values) => {
    const body = {
      ...v,
      amounts_by_generation: Object.fromEntries((lines ?? []).map((l) => [String(l.generation), l.amount])),
    };
    try {
      if (editing?.id) await api(`/contributions/scales/${editing.id}`, { method: "PATCH", body });
      else await api("/contributions/scales", { method: "POST", body });
      message.success("Barème enregistré. Il s'appliquera aux prochaines collectes.");
      setEditing(null);
      load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  const toggle = async (s: Scale) => {
    await api(`/contributions/scales/${s.id}`, { method: "PATCH", body: { active: !s.active } });
    load();
  };

  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <PageHead
        title="Barèmes"
        lead="Reprenez ici les montants fixés par les textes de l'association. Une collecte fige le barème du jour : le modifier ensuite ne change pas les collectes déjà ouvertes."
        actions={
          <Button type="primary" onClick={() => setEditing({ currency: "XAF", default_amount: 0, exempt_under_age: 18, include_spouses: true })}>
            Nouveau barème
          </Button>
        }
      />
      {!scales ? (
        <Spin />
      ) : (
        <Table
          rowKey="id"
          dataSource={scales}
          pagination={false}
          locale={{ emptyText: "Aucun barème. Créez celui de l'association." }}
          columns={[
            { title: "Barème", render: (_, s) => <span className="pname">{s.name}</span> },
            {
              title: "Montants",
              render: (_, s) => (
                <span className="years">
                  {toLines(s)
                    .map((l) => `génération ${l.generation} : ${money(l.amount, s.currency)}`)
                    .join(" ; ")}
                  {s.default_amount ? ` ; autres : ${money(s.default_amount, s.currency)}` : ""}
                </span>
              ),
            },
            {
              title: "Actif",
              width: 90,
              render: (_, s) => <Switch size="small" checked={s.active} onChange={() => toggle(s)} />,
            },
            {
              title: "",
              width: 110,
              render: (_, s) => (
                <Button size="small" onClick={() => setEditing(s)}>
                  Modifier
                </Button>
              ),
            },
          ]}
        />
      )}

      <Modal
        open={!!editing}
        onCancel={() => setEditing(null)}
        footer={null}
        title={editing?.id ? "Modifier le barème" : "Nouveau barème"}
        width={560}
        destroyOnHidden
      >
        {editing && (
          <Form layout="vertical" requiredMark={false} onFinish={save} initialValues={{ ...editing, lines: toLines(editing) }}>
            <div className="form-grid">
              <Form.Item name="name" label="Nom" rules={[{ required: true, min: 2 }]}>
                <Input placeholder="Barème 2026" />
              </Form.Item>
              <Form.Item name="currency" label="Devise">
                <Select
                  disabled={!!editing.id}
                  options={[
                    { value: "XAF", label: "FCFA (Afrique centrale)" },
                    { value: "XOF", label: "FCFA (Afrique de l'Ouest)" },
                    { value: "EUR", label: "Euro" },
                    { value: "USD", label: "Dollar" },
                  ]}
                />
              </Form.Item>
            </div>
            <p style={{ margin: "0 0 8px", fontWeight: 500 }}>Montant par génération</p>
            <Form.List name="lines">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name }) => (
                    <Space key={key} align="baseline" style={{ display: "flex" }}>
                      <Form.Item name={[name, "generation"]} rules={[{ required: true }]}>
                        <InputNumber prefix="Génération" min={0} max={30} style={{ width: 170 }} />
                      </Form.Item>
                      <Form.Item name={[name, "amount"]} rules={[{ required: true }]}>
                        <InputNumber min={0} step={1000} style={{ width: 180 }} placeholder="Montant" />
                      </Form.Item>
                      <MinusCircleOutlined aria-label="Retirer" onClick={() => remove(name)} />
                    </Space>
                  ))}
                  <Button type="dashed" onClick={() => add({ generation: fields.length + 1, amount: 0 })} style={{ marginBottom: 16 }}>
                    Ajouter une génération
                  </Button>
                </>
              )}
            </Form.List>
            <div className="form-grid">
              <Form.Item name="default_amount" label="Autres générations" extra="0 = rien à payer">
                <InputNumber min={0} step={1000} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item name="exempt_under_age" label="Exempter les moins de" extra="ans ; vide = aucune exemption">
                <InputNumber min={0} max={30} style={{ width: "100%" }} />
              </Form.Item>
            </div>
            <Form.Item name="include_spouses" valuePropName="checked">
              <Checkbox>Les conjoints entrés par mariage cotisent aussi</Checkbox>
            </Form.Item>
            <Button type="primary" htmlType="submit" block>
              Enregistrer le barème
            </Button>
          </Form>
        )}
      </Modal>
    </div>
  );
}
