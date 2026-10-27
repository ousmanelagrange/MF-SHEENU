// Comptes inscrits, rôles, branches gérées, et invitations à partager sur WhatsApp.

import { App, Button, Form, Input, Modal, Select, Table } from "antd";
import { useEffect, useState } from "react";
import { PageHead } from "../../components/AppShell";
import { PersonPicker } from "../../components/Person";
import { ShareInviteModal } from "../../components/ShareInviteModal";
import { api } from "../../lib/api";
import { useFamily } from "../../lib/family";
import { ROLE_LABELS, type Invitation, type Member } from "../../types";


export function MembersPage() {
  const { message } = App.useApp();
  const { isAdmin } = useFamily();
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [open, setOpen] = useState(false);
  const [created, setCreated] = useState<{ share_text: string } | null>(null);
  const [branchFor, setBranchFor] = useState<Member | null>(null);

  const load = () => {
    void api<Member[]>("/members").then(setMembers);
    void api<Invitation[]>("/invitations").then(setInvites);
  };
  useEffect(load, []);

  const update = async (m: Member, body: Partial<Member>) => {
    try {
      await api(`/members/${m.id}`, { method: "PATCH", body });
      message.success("Membre mis à jour.");
      load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  const invite = async (v: { person_id?: string; role: string; note?: string }) => {
    try {
      setCreated(await api("/invitations", { method: "POST", body: v }));
      setOpen(false);
      load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  const pending = invites.filter((i) => !i.used_at && new Date(i.expires_at) > new Date());

  return (
    <div className="page">
      <PageHead
        title="Membres et invitations"
        lead="On rejoint la famille uniquement sur invitation. Chaque lien est personnel, valable 7 jours, à usage unique."
        actions={
          <Button type="primary" onClick={() => setOpen(true)}>
            Inviter quelqu'un
          </Button>
        }
      />
      <Table
        rowKey="id"
        dataSource={members}
        pagination={false}
        columns={[
          {
            title: "Membre",
            render: (_, m) => (
              <span>
                <span className="pname">{m.full_name}</span>
                <span style={{ display: "block", color: "var(--muted)", fontSize: 13 }}>
                  {m.email ?? m.phone ?? ""}
                </span>
              </span>
            ),
          },
          {
            title: "Rôle",
            width: 220,
            render: (_, m) =>
              isAdmin ? (
                <Select
                  value={m.role}
                  style={{ width: 190 }}
                  onChange={(role) => update(m, { role })}
                  options={Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))}
                />
              ) : (
                ROLE_LABELS[m.role]
              ),
          },
          {
            title: "Branche gérée",
            width: 200,
            responsive: ["md"],
            render: (_, m) =>
              m.role === "branch_head" && isAdmin ? (
                <Button size="small" onClick={() => setBranchFor(m)}>
                  {m.branch_person_id ? "Changer" : "Choisir"}
                </Button>
              ) : null,
          },
          {
            title: "Depuis",
            dataIndex: "joined_at",
            width: 140,
            responsive: ["sm"],
            render: (d: string) => new Date(d).toLocaleDateString("fr-FR"),
          },
        ]}
      />

      <h2 className="page__title" style={{ fontSize: 22, margin: "48px 0 16px" }}>
        Invitations en attente
      </h2>
      <Table
        rowKey="id"
        dataSource={pending}
        pagination={false}
        locale={{ emptyText: "Aucune invitation en attente." }}
        columns={[
          { title: "Note", dataIndex: "note", render: (n) => n ?? "—" },
          { title: "Rôle", dataIndex: "role", width: 180, render: (r) => ROLE_LABELS[r] },
          {
            title: "Expire le",
            dataIndex: "expires_at",
            width: 160,
            render: (d: string) => new Date(d).toLocaleDateString("fr-FR"),
          },
          {
            title: "",
            width: 120,
            render: (_, i) => (
              <Button
                size="small"
                type="text"
                danger
                onClick={async () => {
                  await api(`/invitations/${i.id}`, { method: "DELETE" });
                  load();
                }}
              >
                Annuler
              </Button>
            ),
          },
        ]}
      />

      <Modal open={open} onCancel={() => setOpen(false)} footer={null} title="Inviter quelqu'un" destroyOnHidden>
        <Form layout="vertical" requiredMark={false} initialValues={{ role: "member" }} onFinish={invite}>
          <Form.Item
            name="person_id"
            label="Sa fiche dans l'arbre"
            extra="Si la personne figure déjà dans l'arbre, son compte y sera relié. Sinon, une fiche sera créée à son arrivée."
          >
            <PersonPicker />
          </Form.Item>
          {isAdmin && (
            <Form.Item name="role" label="Rôle">
              <Select options={Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))} />
            </Form.Item>
          )}
          <Form.Item name="note" label="Note pour vous" extra="Par exemple : Tonton Issa, Douala.">
            <Input maxLength={200} />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            Créer le lien
          </Button>
        </Form>
      </Modal>

      <ShareInviteModal
        title="Lien d'invitation prêt"
        shareText={created?.share_text ?? null}
        onClose={() => setCreated(null)}
      />

      <Modal
        open={!!branchFor}
        onCancel={() => setBranchFor(null)}
        footer={null}
        title={`Branche gérée par ${branchFor?.full_name ?? ""}`}
        destroyOnHidden
      >
        <p style={{ color: "var(--muted)", marginTop: 0 }}>
          Le chef de branche pourra modifier cette personne, ses descendants et leurs conjoints, et y inviter des membres.
        </p>
        <PersonPicker
          value={branchFor?.branch_person_id}
          onChange={async (id) => {
            if (branchFor && id) {
              await update(branchFor, { branch_person_id: id });
              setBranchFor(null);
            }
          }}
        />
      </Modal>
    </div>
  );
}
