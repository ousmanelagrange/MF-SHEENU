// Liste des collectes de la famille : en cours d'abord, puis clôturées.
// Le trésorier et le bureau créent une collecte depuis ici.

import { App, Button, DatePicker, Form, Input, InputNumber, Modal, Select, Spin, Tag } from "antd";
import type { Dayjs } from "dayjs";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { PageHead } from "../../components/AppShell";
import { api } from "../../lib/api";
import { useFamily } from "../../lib/family";
import type { ContributionEvent, Scale } from "../../types";
import { Progress } from "./components/Progress";
import { KIND_LABELS } from "./format";

export function ContributionsPage() {
  const { family } = useFamily();
  const canManage = family?.role === "admin" || family?.role === "treasurer";
  const [events, setEvents] = useState<ContributionEvent[] | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    void api<ContributionEvent[]>("/contributions/events").then(setEvents);
  }, []);

  const open = events?.filter((e) => e.status === "open") ?? [];
  const closed = events?.filter((e) => e.status === "closed") ?? [];

  return (
    <div className="page" style={{ maxWidth: 960 }}>
      <PageHead
        title="Cotisations"
        lead="Chaque collecte calcule ce que doit chacun selon le barème de l'association. Tout le monde voit où en est la collecte ; le trésorier valide les paiements."
        actions={
          canManage && (
            <>
              <Link to="/cotisations/baremes">
                <Button>Barèmes</Button>
              </Link>
              <Button type="primary" onClick={() => setCreating(true)}>
                Nouvelle collecte
              </Button>
            </>
          )
        }
      />
      {!events ? (
        <Spin />
      ) : events.length === 0 ? (
        <p className="empty-note">
          Aucune collecte pour l'instant.{canManage ? " Commencez par saisir le barème de l'association." : ""}
        </p>
      ) : (
        <>
          {open.length > 0 && <EventList title="En cours" events={open} />}
          {closed.length > 0 && <EventList title="Clôturées" events={closed} />}
        </>
      )}
      <CreateEventModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function EventList({ title, events }: { title: string; events: ContributionEvent[] }) {
  return (
    <section className="kin-group" style={{ marginBottom: 36 }}>
      <h2>{title}</h2>
      <ul className="kin-list">
        {events.map((e) => (
          <li key={e.id}>
            <Link to={`/cotisations/${e.id}`} className="event-row">
              <div>
                <span className="pname" style={{ fontSize: 17 }}>
                  {e.title}
                </span>
                <span className="years" style={{ display: "block" }}>
                  {KIND_LABELS[e.kind]}
                  {e.deadline ? `, échéance le ${new Date(e.deadline).toLocaleDateString("fr-FR")}` : ""}
                </span>
              </div>
              <div style={{ minWidth: 260 }}>
                <Progress event={e} compact />
              </div>
              {e.totals.pending > 0 && e.can_manage && <Tag color="gold">À valider</Tag>}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

type NewEvent = {
  title: string;
  kind: ContributionEvent["kind"];
  scale_id?: string;
  deadline?: Dayjs;
  target_amount?: number;
  description?: string;
};

function CreateEventModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [scales, setScales] = useState<Scale[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) void api<Scale[]>("/contributions/scales").then((s) => setScales(s.filter((x) => x.active)));
  }, [open]);

  const submit = async (v: NewEvent) => {
    setSaving(true);
    try {
      const e = await api<ContributionEvent>("/contributions/events", {
        method: "POST",
        body: { ...v, deadline: v.deadline?.format("YYYY-MM-DD") },
      });
      message.success("Collecte créée : les montants dus sont calculés.");
      navigate(`/cotisations/${e.id}`);
    } catch (err) {
      message.error((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onCancel={onClose} footer={null} title="Nouvelle collecte" destroyOnHidden>
      <Form layout="vertical" requiredMark={false} onFinish={submit} initialValues={{ kind: "mourning", scale_id: scales[0]?.id }}>
        <Form.Item name="title" label="Intitulé" rules={[{ required: true, min: 2 }]}>
          <Input placeholder="Deuil de Mama Habiba" />
        </Form.Item>
        <div className="form-grid">
          <Form.Item name="kind" label="Type">
            <Select options={Object.entries(KIND_LABELS).map(([value, label]) => ({ value, label }))} />
          </Form.Item>
          <Form.Item name="deadline" label="Échéance">
            <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" />
          </Form.Item>
        </div>
        <Form.Item
          name="scale_id"
          label="Barème"
          extra="Le barème du jour est figé pour cette collecte. Sans barème, c'est une collecte libre (dons)."
        >
          <Select allowClear placeholder="Collecte libre" options={scales.map((s) => ({ value: s.id, label: s.name }))} />
        </Form.Item>
        <Form.Item name="target_amount" label="Objectif (facultatif)" extra="Pour un projet : montant à réunir.">
          <InputNumber style={{ width: "100%" }} min={0} step={1000} />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input.TextArea autoSize={{ minRows: 2 }} />
        </Form.Item>
        <Button type="primary" htmlType="submit" block loading={saving}>
          Créer la collecte
        </Button>
      </Form>
    </Modal>
  );
}
