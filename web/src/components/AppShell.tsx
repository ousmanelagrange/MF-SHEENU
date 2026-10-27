// Coquille de l'application : barre latérale (marque, famille, navigation) et contenu.

import {
  ApartmentOutlined,
  AuditOutlined,
  BookOutlined,
  CheckSquareOutlined,
  DatabaseOutlined,
  CrownOutlined,
  HomeOutlined,
  MessageOutlined,
  SafetyOutlined,
  MenuOutlined,
  NodeIndexOutlined,
  TeamOutlined,
  UserAddOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import { useGetIdentity, useLogout } from "@refinedev/core";
import { Button, Menu, Spin } from "antd";
import { useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router";
import { useFamily } from "../lib/family";
import { ROLE_LABELS } from "../types";
import { useProposalCounts } from "../features/proposals/useProposalCounts";
import { NtienyaBand, Wordmark } from "./Ntienya";

export function AppShell() {
  const { family, loading, isAdmin, canInvite } = useFamily();
  const { data: me } = useGetIdentity<{ full_name: string }>();
  const { mutate: logout } = useLogout();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const counts = useProposalCounts();
  const pending = counts.to_review || 0;

  if (loading) {
    return (
      <div style={{ display: "grid", placeItems: "center", height: "100vh" }}>
        <Spin />
      </div>
    );
  }
  if (!family) return <Navigate to="/familles" replace />;

  const items = [
    { key: "/", icon: <HomeOutlined />, label: "Accueil" },
    { key: "/fil", icon: <MessageOutlined />, label: "Fil de la famille" },
    { key: "/arbre", icon: <ApartmentOutlined />, label: "Arbre" },
    { key: "/personnes", icon: <TeamOutlined />, label: "Personnes" },
    { key: "/parente", icon: <NodeIndexOutlined />, label: "Lien de parenté" },
    { key: "/memoire", icon: <BookOutlined />, label: "Mémoire" },
    { key: "/cotisations", icon: <WalletOutlined />, label: "Cotisations" },
    {
      key: "/propositions",
      icon: <CheckSquareOutlined />,
      label: (
        <span>
          Propositions
          {pending > 0 && (
            <span className="nav-count" aria-label={`${pending} à valider`}>
              {pending}
            </span>
          )}
        </span>
      ),
    },
    ...(canInvite ? [{ key: "/membres", icon: <UserAddOutlined />, label: "Membres et invitations" }] : []),
    ...(isAdmin
      ? [
          { key: "/titres", icon: <CrownOutlined />, label: "Titres" },
          { key: "/donnees", icon: <DatabaseOutlined />, label: "Données" },
          { key: "/moderation", icon: <SafetyOutlined />, label: "Modération" },
          { key: "/journal", icon: <AuditOutlined />, label: "Journal" },
        ]
      : []),
  ];
  const selected =
    items
      .map((i) => i.key)
      .filter((k) => (k === "/" ? pathname === "/" : pathname.startsWith(k)))
      .sort((a, b) => b.length - a.length)[0] ?? "/";

  return (
    <div className="shell">
      <aside className={`rail${open ? " rail--open" : ""}`}>
        <NtienyaBand height={10} />
        <div className="rail__brand">
          <Wordmark inverted />
        </div>
        <button
          className="rail__family"
          onClick={() => navigate("/familles")}
          title="Changer de famille"
        >
          <span className="rail__family-name">{family.name}</span>
          <span className="rail__family-role">{ROLE_LABELS[family.role] ?? family.role}</span>
        </button>
        <nav>
          <Menu
            mode="inline"
            theme="dark"
            style={{ background: "transparent", borderInlineEnd: 0 }}
            selectedKeys={[selected]}
            items={items}
            onClick={({ key }) => {
              setOpen(false);
              navigate(key);
            }}
          />
        </nav>
        <div className="rail__foot">
          <span>{me?.full_name}</span>
          <button onClick={() => logout()}>Se déconnecter</button>
        </div>
      </aside>
      <div className="main">
        <div className="topbar-mobile">
          <Wordmark />
          <Button icon={<MenuOutlined />} onClick={() => setOpen(!open)} aria-label="Menu" />
        </div>
        <Outlet />
      </div>
    </div>
  );
}

export function PageHead({
  title,
  lead,
  actions,
}: {
  title: React.ReactNode;
  lead?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header className="page__head">
      <div>
        <h1 className="page__title">{title}</h1>
        {lead && <p className="page__lead">{lead}</p>}
      </div>
      {actions && <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>{actions}</div>}
    </header>
  );
}
