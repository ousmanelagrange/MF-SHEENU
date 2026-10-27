// Journal d'audit : chaque ajout, modification ou suppression, avec son auteur.

import { useTable } from "@refinedev/antd";
import { useInvalidate } from "@refinedev/core";
import { Button, Select, Table, Tag } from "antd";
import { PageHead } from "../../components/AppShell";


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
