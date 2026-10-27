import { useTable } from "@refinedev/antd";
import { useInvalidate } from "@refinedev/core";
import {
  App,
  Button,
  ColorPicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
} from "antd";
import { useEffect, useState } from "react";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { PersonPicker } from "../components/Person";
import { useFamily } from "../family";
import { ROLE_LABELS, type Invitation, type Member, type Title } from "../types";

// ---------------- Titres ----------------

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

// ---------------- Membres et invitations ----------------

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

      <Modal open={!!created} onCancel={() => setCreated(null)} footer={null} title="Lien d'invitation prêt">
        {created && (
          <>
            <Input.TextArea value={created.share_text} autoSize readOnly />
            <Space style={{ marginTop: 16 }} wrap>
              <Button
                type="primary"
                href={`https://wa.me/?text=${encodeURIComponent(created.share_text)}`}
                target="_blank"
                rel="noreferrer"
              >
                Partager sur WhatsApp
              </Button>
              <Button
                onClick={() => {
                  void navigator.clipboard.writeText(created.share_text);
                  message.success("Message copié.");
                }}
              >
                Copier le message
              </Button>
            </Space>
          </>
        )}
      </Modal>

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

// ---------------- Journal ----------------

const ACTIONS: Record<string, string> = {
  create: "Création",
  update: "Modification",
  delete: "Suppression",
  archive: "Archivage",
  join: "Arrivée",
};
const ENTITIES: Record<string, string> = {
  person: "fiche",
  parent_child: "filiation",
  union: "union",
  family: "famille",
  membership: "membre",
  invitation: "invitation",
  title: "titre",
  title_holding: "titre attribué",
};

type AuditRow = {
  id: string;
  user_name: string | null;
  action: string;
  entity: string;
  entity_id: string | null;
  after: Record<string, unknown> | null;
  before: Record<string, unknown> | null;
  created_at: string;
};

export function AuditPage() {
  const invalidate = useInvalidate();
  const { tableProps, setFilters } = useTable<AuditRow>({
    resource: "audit",
    pagination: { pageSize: 30 },
    syncWithLocation: false,
  });
  return (
    <div className="page">
      <PageHead
        title="Journal"
        lead="Chaque ajout, modification ou suppression est conservé : qui, quoi, quand."
        actions={<Button onClick={() => invalidate({ resource: "audit", invalidates: ["list"] })}>Actualiser</Button>}
      />
      <Select
        allowClear
        placeholder="Tous les éléments"
        style={{ width: 220, marginBottom: 16 }}
        onChange={(v) => setFilters([{ field: "entity", operator: "eq", value: v }], "replace")}
        options={Object.entries(ENTITIES).map(([value, label]) => ({ value, label }))}
      />
      <Table
        {...tableProps}
        rowKey="id"
        columns={[
          {
            title: "Date",
            dataIndex: "created_at",
            width: 180,
            render: (d: string) =>
              new Date(d).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }),
          },
          { title: "Par", dataIndex: "user_name", width: 180 },
          {
            title: "Action",
            render: (_, r) => (
              <span>
                <Tag bordered={false}>{ACTIONS[r.action] ?? r.action}</Tag>
                {ENTITIES[r.entity] ?? r.entity}
              </span>
            ),
          },
          {
            title: "Détail",
            responsive: ["md"],
            render: (_, r) => {
              const data = r.after ?? r.before ?? {};
              const name = [data.first_name, data.last_name].filter(Boolean).join(" ");
              const keys = Object.keys(r.after ?? {}).filter((k) => !["updated_at", "id", "family_id"].includes(k));
              return (
                <span style={{ color: "var(--muted)" }}>
                  {name || (r.action === "update" ? keys.slice(0, 4).join(", ") : "")}
                </span>
              );
            },
          },
        ]}
      />
    </div>
  );
}
