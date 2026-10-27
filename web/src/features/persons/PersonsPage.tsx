// Liste des personnes, triée par préséance, génération ou nom, avec recherche.

import { useTable } from "@refinedev/antd";
import { Button, Input, Segmented, Table } from "antd";
import { useNavigate } from "react-router";
import { PageHead } from "../../components/AppShell";
import { PersonLine } from "../../components/Person";
import type { PersonSummary } from "../../types";

export function PersonsPage() {
  const navigate = useNavigate();
  const { tableProps, setFilters, setSorters, sorters, tableQuery } = useTable<PersonSummary>({
    resource: "persons",
    pagination: { pageSize: 25 },
    sorters: { initial: [{ field: "precedence", order: "asc" }] },
    syncWithLocation: false,
  });
  const total = tableQuery.data?.total ?? 0;
  const sort = sorters[0]?.field ?? "precedence";

  return (
    <div className="page">
      <PageHead
        title="Personnes"
        lead={`${total} personnes. L'ordre par défaut respecte la préséance : titre, puis génération, puis âge.`}
        actions={
          <Button type="primary" onClick={() => navigate("/personnes/nouvelle")}>
            Ajouter une personne
          </Button>
        }
      />
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        <Input.Search
          placeholder="Nom, prénom, nom traditionnel"
          allowClear
          style={{ maxWidth: 360 }}
          onSearch={(q) => setFilters([{ field: "q", operator: "contains", value: q }], "replace")}
        />
        <Segmented
          value={sort}
          onChange={(v) => setSorters([{ field: String(v), order: "asc" }])}
          options={[
            { label: "Préséance", value: "precedence" },
            { label: "Génération", value: "generation" },
            { label: "Nom", value: "name" },
          ]}
        />
      </div>
      <Table
        {...tableProps}
        rowKey="id"
        onRow={(r) => ({ onClick: () => navigate(`/personnes/${r.id}`), style: { cursor: "pointer" } })}
        columns={[
          {
            title: "Personne",
            render: (_, p) => <PersonLine person={p} link={false} />,
          },
          {
            title: "Génération",
            dataIndex: "generation",
            width: 120,
            render: (g) => g ?? "—",
            responsive: ["sm"],
          },
          {
            title: "Compte",
            dataIndex: "has_account",
            width: 120,
            render: (v: boolean) => (v ? "Inscrit" : ""),
            responsive: ["md"],
          },
        ]}
      />
    </div>
  );
}
