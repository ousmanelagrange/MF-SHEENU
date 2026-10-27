// Propositions : celles que je dois valider (chef de branche, bureau) et celles que j'ai envoyées.

import { App, Button, Empty, Input, Modal, Segmented, Space, Spin, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { PageHead } from "../../components/AppShell";
import { api } from "../../lib/api";
import { useProposalCounts } from "./useProposalCounts";

type Proposal = {
  id: string;
  kind: string;
  summary: string;
  message: string | null;
  status: "pending" | "accepted" | "rejected" | "withdrawn";
  author_name: string | null;
  reviewer_name: string | null;
  review_note: string | null;
  result_id: string | null;
  created_at: string;
  reviewed_at: string | null;
  can_review: boolean;
};

const STATUS: Record<Proposal["status"], { label: string; color: string }> = {
  pending: { label: "En attente", color: "gold" },
  accepted: { label: "Acceptée", color: "green" },
  rejected: { label: "Refusée", color: "red" },
  withdrawn: { label: "Retirée", color: "default" },
};

const when = (d: string) => new Date(d).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });

export function ProposalsPage() {
  const counts = useProposalCounts();
  const [view, setView] = useState<"review" | "mine">("review");
  const [items, setItems] = useState<Proposal[] | null>(null);
  const [rejecting, setRejecting] = useState<Proposal | null>(null);

  const load = useCallback(() => {
    setItems(null);
    const query = view === "review" ? { view, status: "pending" } : { view, status: "any" };
    void api<Proposal[]>("/proposals", { query }).then(setItems);
  }, [view]);
  useEffect(load, [load]);

  return (
    <div className="page" style={{ maxWidth: 880 }}>
      <PageHead
        title="Propositions"
        lead="Quand une modification sort du périmètre de son auteur, elle attend ici la validation du chef de branche concerné ou du bureau."
      />
      <Segmented
        value={view}
        onChange={(v) => setView(v as "review" | "mine")}
        options={[
          { label: `À valider (${counts.to_review})`, value: "review" },
          { label: `Mes propositions (${counts.mine_pending} en attente)`, value: "mine" },
        ]}
        style={{ marginBottom: 20 }}
      />
      {!items ? (
        <Spin style={{ display: "block", margin: 32 }} />
      ) : items.length === 0 ? (
        <Empty
          description={view === "review" ? "Aucune proposition à valider." : "Vous n'avez envoyé aucune proposition."}
        />
      ) : (
        <ul className="kin-list">
          {items.map((p) => (
            <ProposalItem key={p.id} p={p} view={view} onChanged={load} onReject={() => setRejecting(p)} />
          ))}
        </ul>
      )}
      <RejectModal proposal={rejecting} onClose={() => setRejecting(null)} onDone={load} />
    </div>
  );
}

function ProposalItem({
  p,
  view,
  onChanged,
  onReject,
}: {
  p: Proposal;
  view: "review" | "mine";
  onChanged: () => void;
  onReject: () => void;
}) {
  const { message } = App.useApp();
  const [busy, setBusy] = useState(false);

  const act = async (path: string, done: string) => {
    setBusy(true);
    try {
      await api(`/proposals/${p.id}/${path}`, { method: "POST", body: {} });
      message.success(done);
      onChanged();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li style={{ padding: "16px 4px", display: "block" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start" }}>
        <div>
          <p className="pname" style={{ fontSize: 17, margin: 0 }}>
            {p.summary}
          </p>
          <p className="years" style={{ margin: "4px 0 0" }}>
            {view === "review" ? `Proposée par ${p.author_name ?? "un membre"}, ` : ""}
            {when(p.created_at)}
          </p>
          {p.message && <p style={{ margin: "10px 0 0", maxWidth: "62ch" }}>« {p.message} »</p>}
          {p.status !== "pending" && p.reviewer_name && (
            <p className="years" style={{ margin: "8px 0 0" }}>
              {STATUS[p.status].label} par {p.reviewer_name}
              {p.review_note ? ` : ${p.review_note}` : ""}
            </p>
          )}
          {p.status === "accepted" && p.result_id && p.kind.includes("person") && p.kind !== "archive_person" && (
            <Link to={`/personnes/${p.result_id}`}>Voir la fiche</Link>
          )}
        </div>
        <Space>
          {view === "mine" && <Tag color={STATUS[p.status].color}>{STATUS[p.status].label}</Tag>}
          {p.can_review && (
            <>
              <Button type="primary" loading={busy} onClick={() => act("accept", "Proposition acceptée et appliquée.")}>
                Accepter
              </Button>
              <Button onClick={onReject}>Refuser</Button>
            </>
          )}
          {view === "mine" && p.status === "pending" && (
            <Button type="text" loading={busy} onClick={() => act("withdraw", "Proposition retirée.")}>
              Retirer
            </Button>
          )}
        </Space>
      </div>
    </li>
  );
}

function RejectModal({ proposal, onClose, onDone }: { proposal: Proposal | null; onClose: () => void; onDone: () => void }) {
  const { message } = App.useApp();
  const [note, setNote] = useState("");
  const submit = async () => {
    if (!proposal) return;
    try {
      await api(`/proposals/${proposal.id}/reject`, { method: "POST", body: { note } });
      message.success("Proposition refusée.");
      setNote("");
      onClose();
      onDone();
    } catch (e) {
      message.error((e as Error).message);
    }
  };
  return (
    <Modal
      open={!!proposal}
      title="Refuser la proposition"
      okText="Refuser"
      cancelText="Annuler"
      okButtonProps={{ danger: true, disabled: !note.trim() }}
      onOk={submit}
      onCancel={onClose}
      destroyOnHidden
    >
      <p style={{ marginTop: 0 }}>{proposal?.summary}</p>
      <Input.TextArea
        autoFocus
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Motif du refus, visible par l'auteur"
        autoSize={{ minRows: 3 }}
      />
    </Modal>
  );
}
