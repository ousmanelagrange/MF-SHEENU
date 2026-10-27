// Une collecte : avancement, état de chaque personne (transparent pour tous),
// paiements, récapitulatif WhatsApp, export pour Excel, clôture.

import { App, Button, Input, Popconfirm, Segmented, Spin, Table, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router";
import { PageHead } from "../../components/AppShell";
import { PersonLine } from "../../components/Person";
import { api } from "../../lib/api";
import type { ContributionEvent, DueRow, DueStatus, Payment } from "../../types";
import { download } from "../tree/exporter";
import { DueEditModal } from "./components/DueEditModal";
import { PaymentModal } from "./components/PaymentModal";
import { PaymentsList } from "./components/PaymentsList";
import { Progress } from "./components/Progress";
import { PayOnlineModal } from "./components/PayOnlineModal";
import { RecapModal } from "./components/RecapModal";
import { RemindersModal } from "./components/RemindersModal";
import { KIND_LABELS, STATUS_COLORS, STATUS_LABELS, money } from "./format";

type Filter = DueStatus | "any";

export function EventPage() {
  const { id = "" } = useParams();
  const { message } = App.useApp();
  const [event, setEvent] = useState<ContributionEvent | null>(null);
  const [rows, setRows] = useState<DueRow[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [tab, setTab] = useState<"dues" | "payments">("dues");
  const [filter, setFilter] = useState<Filter>("any");
  const [q, setQ] = useState("");
  const [paying, setPaying] = useState<{ personId?: string } | null>(null);
  const [reminding, setReminding] = useState(false);
  const [payingOnline, setPayingOnline] = useState(false);
  const [online, setOnline] = useState(false);
  useEffect(() => void api<{ enabled: boolean }>("/contributions/online").then((o) => setOnline(o.enabled)), []);
  const [recap, setRecap] = useState(false);
  const [editing, setEditing] = useState<DueRow | null>(null);

  const load = useCallback(() => {
    void api<ContributionEvent>(`/contributions/events/${id}`).then(setEvent);
    void api<DueRow[]>(`/contributions/events/${id}/dues`).then(setRows);
    void api<Payment[]>(`/contributions/events/${id}/payments`).then(setPayments);
  }, [id]);
  useEffect(load, [load]);

  if (!event) return <Spin style={{ margin: 48 }} />;

  const open = event.status === "open";
  const pending = payments.filter((p) => p.status === "declared").length;
  const shown = rows.filter(
    (r) => (filter === "any" || r.status === filter) && r.person.display_name.toLowerCase().includes(q.toLowerCase()),
  );

  const exportCsv = async () => {
    const res = await api<Response>(`/contributions/events/${id}/export.csv`, { raw: true });
    download(await res.blob(), `${event.title}.csv`);
  };

  const close = async () => {
    try {
      await api(`/contributions/events/${id}/close`, { method: "POST" });
      message.success("Collecte clôturée. Son historique est désormais définitif.");
      load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  return (
    <div className="page" style={{ maxWidth: 1000 }}>
      <PageHead
        title={event.title}
        lead={[
          KIND_LABELS[event.kind],
          event.deadline ? `échéance le ${new Date(event.deadline).toLocaleDateString("fr-FR")}` : null,
          open ? null : "clôturée",
        ]
          .filter(Boolean)
          .join(", ")}
        actions={
          <>
            {open && (
              <Button type="primary" onClick={() => setPaying({})}>
                Déclarer un paiement
              </Button>
            )}
            {open && online && <Button onClick={() => setPayingOnline(true)}>Payer par Mobile Money</Button>}
            {open && event.can_manage && <Button onClick={() => setReminding(true)}>Relancer</Button>}
            <Button onClick={() => setRecap(true)}>Récapitulatif WhatsApp</Button>
            <Button onClick={exportCsv}>Exporter pour Excel</Button>
            {event.can_manage && open && (
              <Popconfirm
                title="Clôturer la collecte ?"
                description="Plus aucun paiement ni ajustement ne sera possible."
                okText="Clôturer"
                cancelText="Annuler"
                onConfirm={close}
              >
                <Button>Clôturer</Button>
              </Popconfirm>
            )}
          </>
        }
      />
      {event.description && <p className="bio" style={{ marginTop: -12, marginBottom: 24 }}>{event.description}</p>}
      <Progress event={event} />

      <Segmented
        value={tab}
        onChange={(v) => setTab(v as "dues" | "payments")}
        options={[
          { label: `État par personne (${rows.length})`, value: "dues" },
          { label: event.can_manage && pending ? `Paiements (${pending} à valider)` : "Paiements", value: "payments" },
        ]}
        style={{ margin: "32px 0 16px" }}
      />

      {tab === "dues" ? (
        <>
          <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
            <Input.Search placeholder="Rechercher un nom" allowClear style={{ maxWidth: 280 }} onChange={(e) => setQ(e.target.value)} />
            <Segmented
              value={filter}
              onChange={(v) => setFilter(v as Filter)}
              options={[
                { label: "Tous", value: "any" },
                { label: "Non payés", value: "unpaid" },
                { label: "Partiels", value: "partial" },
                { label: "À jour", value: "paid" },
              ]}
            />
          </div>
          <Table
            rowKey={(r) => r.person.id}
            dataSource={shown}
            pagination={{ pageSize: 50, hideOnSinglePage: true }}
            columns={[
              { title: "Personne", render: (_, r) => <PersonLine person={r.person} size={32} /> },
              {
                title: "Dû",
                width: 140,
                align: "right",
                render: (_, r) => (r.amount ? money(r.amount, event.currency) : "—"),
              },
              { title: "Payé", width: 140, align: "right", render: (_, r) => money(r.paid, event.currency) },
              {
                title: "Statut",
                width: 150,
                render: (_, r) => (
                  <>
                    <Tag color={STATUS_COLORS[r.status]}>{STATUS_LABELS[r.status]}</Tag>
                    {r.note && <span className="years" style={{ display: "block" }}>{r.note}</span>}
                  </>
                ),
              },
              {
                title: "",
                width: 170,
                render: (_, r) =>
                  open && (
                    <span style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
                      {r.status !== "paid" && r.status !== "exempt" && (
                        <Button size="small" type="text" onClick={() => setPaying({ personId: r.person.id })}>
                          Payer
                        </Button>
                      )}
                      {event.can_manage && r.due_id && (
                        <Button size="small" type="text" onClick={() => setEditing(r)}>
                          Ajuster
                        </Button>
                      )}
                    </span>
                  ),
              },
            ]}
          />
        </>
      ) : (
        <PaymentsList event={event} payments={payments} onChanged={load} />
      )}

      <PaymentModal
        event={event}
        open={!!paying}
        defaultPersonId={paying?.personId}
        onClose={() => setPaying(null)}
        onDone={load}
      />
      <RecapModal eventId={event.id} open={recap} onClose={() => setRecap(false)} />
      <RemindersModal eventId={event.id} open={reminding} onClose={() => setReminding(false)} />
      <PayOnlineModal event={event} open={payingOnline} onClose={() => setPayingOnline(false)} onDone={load} />
      <DueEditModal row={editing} onClose={() => setEditing(null)} onDone={load} />
    </div>
  );
}
