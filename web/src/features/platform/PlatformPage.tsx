// Supervision de la plateforme (opérateur) : santé, trafic, sécurité, comptes, familles,
// journal de l'opérateur. On y voit des comptes et des nombres, jamais le contenu des familles ;
// chaque consultation sensible et chaque action est inscrite au journal.

import { App, Button, Empty, Input, Modal, Segmented, Select, Space, Spin, Table, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { NtienyaBand, Wordmark } from "../../components/Ntienya";
import { api, ApiError } from "../../lib/api";
import { ACTION_LABELS, bytes, duration, EVENT_LABELS, SEVERITY, when } from "./labels";
import { TrafficChart } from "./TrafficChart";

type Tab = "overview" | "security" | "users" | "families" | "audit";

export function PlatformPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [denied, setDenied] = useState(false);
  useEffect(() => {
    api("/platform/overview", { family: false }).catch((e) => e instanceof ApiError && e.status === 403 && setDenied(true));
  }, []);

  return (
    <div style={{ minHeight: "100vh", background: "var(--cotton)" }}>
      <NtienyaBand height={10} />
      <div className="page">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
          <Wordmark />
          <Space size="large">
            <Link to="/familles">Vos familles</Link>
            <Link to="/compte">Mon compte</Link>
          </Space>
        </div>
        <h1 className="page__title">Supervision de la plateforme</h1>
        <p className="page__lead">
          Santé, trafic et sécurité de Sheenu. Vous voyez des comptes et des nombres, jamais le contenu des familles. Vos consultations et vos
          actions sont inscrites au journal.
        </p>
        {denied ? (
          <Empty description="Réservé à l'opérateur de la plateforme." style={{ marginTop: 48 }} />
        ) : (
          <>
            <nav className="tabs-nav" style={{ marginTop: 24 }}>
              {(
                [
                  ["overview", "Vue d'ensemble"],
                  ["security", "Sécurité"],
                  ["users", "Comptes"],
                  ["families", "Familles"],
                  ["audit", "Journal de l'opérateur"],
                ] as const
              ).map(([k, label]) => (
                <a key={k} className={tab === k ? "is-active" : undefined} onClick={() => setTab(k)} role="tab" aria-selected={tab === k}>
                  {label}
                </a>
              ))}
            </nav>
            {tab === "overview" && <Overview />}
            {tab === "security" && <Security />}
            {tab === "users" && <Users />}
            {tab === "families" && <Families />}
            {tab === "audit" && <Audit />}
          </>
        )}
      </div>
    </div>
  );
}

type OverviewData = {
  health: Record<string, string | number | boolean | null>;
  users: Record<string, number>;
  families: Record<string, number>;
  traffic_24h: Record<string, number>;
  security_24h: Record<string, number>;
};

function Overview() {
  const { message } = App.useApp();
  const [data, setData] = useState<OverviewData | null>(null);
  const [traffic, setTraffic] = useState([]);
  const load = useCallback(() => {
    void api<OverviewData>("/platform/overview", { family: false }).then(setData);
    void api<never[]>("/platform/traffic", { family: false, query: { hours: 24 } }).then(setTraffic);
  }, []);
  useEffect(() => {
    load();
    const id = window.setInterval(load, 30_000);
    return () => window.clearInterval(id);
  }, [load]);
  if (!data) return <Spin />;
  const h = data.health;
  const t = data.traffic_24h;
  const errorRate = t.requests ? ((100 * t.errors_5xx) / t.requests).toFixed(2) : "0";

  return (
    <>
      <div className="stat-strip">
        <div>
          <b>{data.users.total}</b>
          <span>comptes, {data.users.active_7d} actifs cette semaine</span>
        </div>
        <div>
          <b>{data.families.total}</b>
          <span>familles, {data.families.memberships} adhésions</span>
        </div>
        <div>
          <b>{t.requests.toLocaleString("fr-FR")}</b>
          <span>requêtes en 24 h, {t.avg_ms} ms en moyenne</span>
        </div>
        <div className={data.security_24h.critical ? "is-alert" : undefined}>
          <b>{data.security_24h.critical}</b>
          <span>alertes critiques en 24 h, {data.security_24h.warning} à surveiller</span>
        </div>
      </div>

      <div className="platform-grid">
        <section className="kin-group">
          <h2>Trafic des dernières 24 heures</h2>
          <TrafficChart data={traffic} />
          <p className="years">
            {t.errors_5xx} erreur(s) serveur ({errorRate} %), {t.errors_4xx} requêtes refusées (droits, validation, débit), temps maximal {t.max_ms} ms.
          </p>
        </section>
        <section className="kin-group">
          <h2>Santé</h2>
          <dl className="facts health">
            <dt>Isolement des familles</dt>
            <dd>{h.rls_enforced ? <Tag color="green">Actif</Tag> : <Tag color="red">DÉSACTIVÉ : rôle de base trop puissant</Tag>}</dd>
            <dt>Environnement</dt>
            <dd>{String(h.environment)}</dd>
            <dt>Base de données</dt>
            <dd>
              répond en {String(h.database_ms)} ms, schéma {String(h.migration)}
            </dd>
            <dt>Stockage</dt>
            <dd>
              {h.storage === "s3" ? "Cloudflare R2" : "disque local"}
              {h.media_bytes !== null ? `, ${bytes(Number(h.media_bytes))}` : ""}
            </dd>
            <dt>Messagerie</dt>
            <dd>{h.messaging === "share" ? "liens WhatsApp" : "WhatsApp Business"}</dd>
            <dt>Paiement en ligne</dt>
            <dd>{h.payments === "none" ? "désactivé" : String(h.payments)}</dd>
            <dt>Limitation de débit</dt>
            <dd>{h.rate_limit ? "active" : <Tag color="red">désactivée</Tag>}</dd>
            <dt>En service depuis</dt>
            <dd>{duration(Number(h.uptime_s))}</dd>
            <dt>Comptes</dt>
            <dd>
              {data.users.new_7d} nouveaux cette semaine, {data.users.locked} verrouillé(s), {data.users.disabled} suspendu(s), {data.users.sessions} session(s) ouvertes
            </dd>
          </dl>
          <Button
            style={{ marginTop: 16 }}
            onClick={async () => {
              const r = await api<{ idempotency_keys: number; metrics: number }>("/platform/maintenance/purge", { method: "POST", family: false });
              message.success(`Purge faite : ${r.idempotency_keys} clé(s) d'envoi, ${r.metrics} minute(s) de compteurs.`);
            }}
          >
            Purger les données techniques anciennes
          </Button>
        </section>
      </div>
    </>
  );
}

type Event = { id: string; at: string; kind: string; severity: string; user: string | null; ip: string | null; path: string | null; detail: Record<string, string> };

function Security() {
  const [severity, setSeverity] = useState<string>("all");
  const [kind, setKind] = useState<string | undefined>();
  const [items, setItems] = useState<Event[] | null>(null);
  useEffect(() => {
    setItems(null);
    void api<Event[]>("/platform/events", { family: false, query: { severity: severity === "all" ? undefined : severity, kind, limit: 300 } }).then(setItems);
  }, [severity, kind]);

  return (
    <>
      <div className="toolbar">
        <Segmented
          value={severity}
          onChange={(v) => setSeverity(String(v))}
          options={[
            { label: "Tout", value: "all" },
            { label: "Critique", value: "critical" },
            { label: "Alerte", value: "warning" },
            { label: "Info", value: "info" },
          ]}
        />
        <Select
          allowClear
          placeholder="Type d'événement"
          style={{ minWidth: 260 }}
          value={kind}
          onChange={setKind}
          options={Object.entries(EVENT_LABELS).map(([value, label]) => ({ value, label }))}
        />
      </div>
      <Table
        rowKey="id"
        loading={!items}
        dataSource={items ?? []}
        size="middle"
        pagination={{ pageSize: 25, showSizeChanger: false }}
        columns={[
          { title: "Quand", dataIndex: "at", width: 150, render: when },
          { title: "Gravité", dataIndex: "severity", width: 100, render: (s: string) => <Tag color={SEVERITY[s]?.color}>{SEVERITY[s]?.label ?? s}</Tag> },
          { title: "Événement", dataIndex: "kind", render: (k: string) => EVENT_LABELS[k] ?? k },
          { title: "Compte", dataIndex: "user", render: (u) => u ?? "—" },
          { title: "Adresse IP", dataIndex: "ip", width: 140, render: (ip) => ip ?? "—" },
          {
            title: "Détail",
            render: (_, e) => (
              <span className="years">
                {[e.path, ...Object.entries(e.detail).map(([k, v]) => `${k} : ${v}`)].filter(Boolean).join(", ")}
              </span>
            ),
          },
        ]}
      />
    </>
  );
}

type Account = {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  created_at: string;
  last_login_at: string | null;
  active: boolean;
  locked_until: string | null;
  failed_logins: number;
  operator: boolean;
  families: number;
  sessions: number;
};

function Users() {
  const { message } = App.useApp();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<string>("all");
  const [items, setItems] = useState<Account[] | null>(null);
  const [acting, setActing] = useState<{ user: Account; action: "disable" | "enable" | "revoke-sessions" } | null>(null);
  const [reason, setReason] = useState("");

  const load = useCallback(() => {
    void api<Account[]>("/platform/users", { family: false, query: { q: q || undefined, status: status === "all" ? undefined : status } }).then(setItems);
  }, [q, status]);
  useEffect(() => {
    const id = window.setTimeout(load, 250);
    return () => window.clearTimeout(id);
  }, [load]);

  const act = async () => {
    if (!acting) return;
    await api(`/platform/users/${acting.user.id}/${acting.action}`, { method: "POST", body: { reason }, family: false });
    message.success("Fait, et inscrit au journal.");
    setActing(null);
    setReason("");
    load();
  };

  return (
    <>
      <div className="toolbar">
        <Input.Search placeholder="Nom, e-mail ou téléphone" allowClear value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 320 }} />
        <Segmented
          value={status}
          onChange={(v) => setStatus(String(v))}
          options={[
            { label: "Tous", value: "all" },
            { label: "Verrouillés", value: "locked" },
            { label: "Suspendus", value: "disabled" },
            { label: "Opérateurs", value: "operators" },
          ]}
        />
      </div>
      <Table
        rowKey="id"
        loading={!items}
        dataSource={items ?? []}
        size="middle"
        pagination={{ pageSize: 25, showSizeChanger: false }}
        columns={[
          {
            title: "Compte",
            render: (_, u) => (
              <span>
                <span className="pname">{u.full_name}</span>
                <span className="years" style={{ display: "block" }}>
                  {u.email ?? u.phone}
                </span>
              </span>
            ),
          },
          { title: "Inscrit", dataIndex: "created_at", width: 140, render: when },
          { title: "Dernière connexion", dataIndex: "last_login_at", width: 160, render: when },
          { title: "Familles", dataIndex: "families", width: 90, align: "right" },
          { title: "Appareils", dataIndex: "sessions", width: 100, align: "right" },
          {
            title: "État",
            width: 170,
            render: (_, u) => (
              <Space size={4} wrap>
                {!u.active && <Tag color="red">Suspendu</Tag>}
                {u.locked_until && <Tag color="gold">Verrouillé</Tag>}
                {u.operator && <Tag color="blue">Opérateur</Tag>}
                {u.active && !u.locked_until && <Tag>Actif</Tag>}
              </Space>
            ),
          },
          {
            title: "",
            width: 280,
            render: (_, u) => (
              <Space size={4} wrap>
                {u.locked_until && (
                  <Button
                    size="small"
                    onClick={async () => {
                      await api(`/platform/users/${u.id}/unlock`, { method: "POST", family: false });
                      load();
                    }}
                  >
                    Déverrouiller
                  </Button>
                )}
                {u.sessions > 0 && (
                  <Button size="small" onClick={() => setActing({ user: u, action: "revoke-sessions" })}>
                    Déconnecter partout
                  </Button>
                )}
                {u.active ? (
                  !u.operator && (
                    <Button size="small" danger onClick={() => setActing({ user: u, action: "disable" })}>
                      Suspendre
                    </Button>
                  )
                ) : (
                  <Button size="small" onClick={() => setActing({ user: u, action: "enable" })}>
                    Réactiver
                  </Button>
                )}
              </Space>
            ),
          },
        ]}
      />
      <Modal
        open={!!acting}
        title={
          acting
            ? `${acting.action === "disable" ? "Suspendre" : acting.action === "enable" ? "Réactiver" : "Déconnecter partout"} : ${acting.user.full_name}`
            : ""
        }
        okText="Confirmer"
        cancelText="Annuler"
        okButtonProps={{ disabled: reason.trim().length < 3, danger: acting?.action === "disable" }}
        onOk={act}
        onCancel={() => setActing(null)}
      >
        <p className="modal-note">
          {acting?.action === "disable"
            ? "Le compte ne pourra plus se connecter et tous ses appareils sont déconnectés immédiatement. Ses données familiales ne sont pas touchées."
            : acting?.action === "enable"
              ? "Le compte pourra de nouveau se connecter."
              : "Tous les appareils du compte devront se reconnecter (téléphone perdu, soupçon de piratage)."}
        </p>
        <Input.TextArea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Motif, inscrit au journal" autoSize={{ minRows: 2 }} />
      </Modal>
    </>
  );
}

type FamilyRow = { id: string; name: string; created_at: string; merged: boolean; members: number; persons: number; posts: number; narratives: number; last_activity: string | null };

function Families() {
  const [items, setItems] = useState<FamilyRow[] | null>(null);
  useEffect(() => void api<FamilyRow[]>("/platform/families", { family: false }).then(setItems), []);
  return (
    <>
      <p className="modal-note">Des nombres seulement : la supervision n'ouvre pas les familles et ne lit pas leur contenu.</p>
      <Table
        rowKey="id"
        loading={!items}
        dataSource={items ?? []}
        size="middle"
        pagination={{ pageSize: 25, showSizeChanger: false }}
        columns={[
          { title: "Famille", dataIndex: "name", render: (n, f) => <span className="pname">{n}{f.merged && <Tag style={{ marginLeft: 8 }}>réunie</Tag>}</span> },
          { title: "Créée", dataIndex: "created_at", width: 140, render: when },
          { title: "Membres", dataIndex: "members", width: 100, align: "right" },
          { title: "Fiches", dataIndex: "persons", width: 90, align: "right" },
          { title: "Publications", dataIndex: "posts", width: 120, align: "right" },
          { title: "Récits", dataIndex: "narratives", width: 90, align: "right" },
          { title: "Dernière activité", dataIndex: "last_activity", width: 160, render: when },
        ]}
      />
    </>
  );
}

type AuditRow = { id: string; at: string; operator: string | null; action: string; target: string | null; detail: Record<string, string>; ip: string | null };

function Audit() {
  const [items, setItems] = useState<AuditRow[] | null>(null);
  useEffect(() => void api<AuditRow[]>("/platform/audit", { family: false }).then(setItems), []);
  return (
    <>
      <p className="modal-note">Ce journal est en ajout seul : la base de données refuse toute modification ou suppression, y compris par l'opérateur.</p>
      <Table
        rowKey="id"
        loading={!items}
        dataSource={items ?? []}
        size="middle"
        pagination={{ pageSize: 25, showSizeChanger: false }}
        columns={[
          { title: "Quand", dataIndex: "at", width: 150, render: when },
          { title: "Opérateur", dataIndex: "operator", width: 180, render: (o) => o ?? "ligne de commande" },
          { title: "Action", dataIndex: "action", render: (a: string) => ACTION_LABELS[a] ?? a },
          {
            title: "Détail",
            render: (_, a) => (
              <span className="years">{[a.target ? `compte ${a.target.slice(0, 8)}…` : null, ...Object.entries(a.detail).filter(([, v]) => v).map(([k, v]) => `${k} : ${v}`)].filter(Boolean).join(", ")}</span>
            ),
          },
          { title: "Adresse IP", dataIndex: "ip", width: 140, render: (ip) => ip ?? "—" },
        ]}
      />
    </>
  );
}
