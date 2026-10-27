// Demandes de rattachement en attente (bureau, chefs de branche) : lire comment la personne
// se situe, puis la placer dans l'arbre ou refuser avec un motif.

import { App, Button, Form, Input, Modal, Radio, Select } from "antd";
import { useEffect, useState } from "react";
import { PersonPicker } from "../../components/Person";
import { api } from "../../lib/api";
import { useFamily } from "../../lib/family";
import type { JoinRequest } from "../../types";
import { ago } from "../social/format";

type Placement = "child" | "existing" | "new";

export function JoinRequestsSection() {
  const { message } = App.useApp();
  const { family } = useFamily();
  const [items, setItems] = useState<JoinRequest[]>([]);
  const [accepting, setAccepting] = useState<JoinRequest | null>(null);
  const [rejecting, setRejecting] = useState<JoinRequest | null>(null);
  const [placement, setPlacement] = useState<Placement>("child");
  const [form] = Form.useForm();

  const load = () => void api<JoinRequest[]>("/join-requests").then(setItems);
  useEffect(load, []);

  const accept = async (v: { anchor?: string; role?: string }) => {
    if (!accepting) return;
    await api(`/join-requests/${accepting.id}/accept`, {
      method: "POST",
      body: {
        person_id: placement === "existing" ? v.anchor : null,
        parent_id: placement === "child" ? v.anchor : null,
        role: v.role ?? "member",
      },
    });
    message.success(`${accepting.first_name} fait maintenant partie de la famille.`);
    setAccepting(null);
    form.resetFields();
    load();
  };

  const reject = async (v: { note: string }) => {
    if (!rejecting) return;
    await api(`/join-requests/${rejecting.id}/reject`, { method: "POST", body: v });
    setRejecting(null);
    load();
  };

  if (items.length === 0) return null;
  return (
    <section style={{ marginBottom: 40 }}>
      <h2 className="page__title" style={{ fontSize: 22, margin: "0 0 12px" }}>
        Demandes de rattachement <span className="pending-note">{items.length}</span>
      </h2>
      <ul className="join-requests">
        {items.map((r) => (
          <li key={r.id}>
            <div>
              <p className="pname" style={{ margin: 0, fontSize: 17 }}>
                {r.first_name} {r.last_name}
                {r.birth_year ? <span className="years"> né(e) en {r.birth_year}</span> : null}
              </p>
              <blockquote>{r.lineage}</blockquote>
              <p className="years" style={{ margin: 0 }}>
                {[r.village, r.country, r.phone, `compte ${r.account_name}`, ago(r.created_at)].filter(Boolean).join(", ")}
              </p>
            </div>
            <div className="join-requests__actions">
              <Button type="primary" onClick={() => setAccepting(r)}>
                Rattacher
              </Button>
              <Button onClick={() => setRejecting(r)}>Refuser</Button>
            </div>
          </li>
        ))}
      </ul>

      <Modal
        open={!!accepting}
        title={accepting ? `Rattacher ${accepting.first_name} ${accepting.last_name ?? ""}` : ""}
        okText="Rattacher"
        cancelText="Annuler"
        onOk={() => form.submit()}
        onCancel={() => setAccepting(null)}
        destroyOnHidden
      >
        {accepting && <blockquote className="modal-note">{accepting.lineage}</blockquote>}
        <Form form={form} layout="vertical" onFinish={accept} requiredMark={false}>
          <Radio.Group value={placement} onChange={(e) => setPlacement(e.target.value)} style={{ display: "grid", gap: 8, marginBottom: 16 }}>
            <Radio value="child">Comme enfant d'une personne de l'arbre</Radio>
            <Radio value="existing">Sur une fiche qui existe déjà</Radio>
            <Radio value="new">Sur une nouvelle fiche, à relier plus tard</Radio>
          </Radio.Group>
          {placement !== "new" && (
            <Form.Item
              name="anchor"
              label={placement === "child" ? "Son père ou sa mère" : "Sa fiche"}
              rules={[{ required: true, message: "Choisissez une personne." }]}
            >
              <PersonPicker />
            </Form.Item>
          )}
          {family?.role === "admin" && (
            <Form.Item name="role" label="Rôle" initialValue="member">
              <Select
                options={[
                  { value: "member", label: "Membre" },
                  { value: "branch_head", label: "Chef de branche" },
                ]}
              />
            </Form.Item>
          )}
        </Form>
      </Modal>

      <Modal open={!!rejecting} title="Refuser la demande" footer={null} onCancel={() => setRejecting(null)} destroyOnHidden>
        <Form layout="vertical" onFinish={reject} requiredMark={false}>
          <Form.Item name="note" label="Motif, visible par la personne" rules={[{ required: true, min: 2, message: "Indiquez un motif." }]}>
            <Input.TextArea autoSize={{ minRows: 2 }} placeholder="Nous ne retrouvons pas ce lien ; précisez le nom de votre grand-père." />
          </Form.Item>
          <Button type="primary" htmlType="submit">
            Refuser
          </Button>
        </Form>
      </Modal>
    </section>
  );
}
