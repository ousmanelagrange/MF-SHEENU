// Modération (bureau, secrétaire) : signalements en attente, à masquer ou à classer.

import { App, Button, Empty, Space, Spin } from "antd";
import { useEffect, useState } from "react";
import { PageHead } from "../../components/AppShell";
import { api } from "../../lib/api";
import { ago } from "./format";

type ReportItem = { id: string; excerpt: string; reason: string; reporter_name: string; created_at: string; comment_id: string | null };

export function ModerationPage() {
  const { message } = App.useApp();
  const [items, setItems] = useState<ReportItem[] | null>(null);
  const load = () => void api<ReportItem[]>("/reports").then(setItems);
  useEffect(load, []);

  const resolve = async (r: ReportItem, hide: boolean) => {
    await api(`/reports/${r.id}/resolve`, { method: "POST", query: { hide } });
    message.success(hide ? "Contenu masqué." : "Signalement classé.");
    load();
  };

  return (
    <div className="page" style={{ maxWidth: 820 }}>
      <PageHead title="Modération" lead="Les membres signalent ici les messages déplacés. Masquer un contenu le retire du fil pour tous, sauf pour la modération." />
      {!items ? (
        <Spin />
      ) : items.length === 0 ? (
        <Empty description="Aucun signalement en attente." />
      ) : (
        <ul className="kin-list">
          {items.map((r) => (
            <li key={r.id} style={{ padding: "14px 4px", display: "flex", gap: 16, justifyContent: "space-between" }}>
              <div>
                <p style={{ margin: 0 }}>« {r.excerpt} »</p>
                <p className="years" style={{ margin: "4px 0 0" }}>
                  {r.comment_id ? "Commentaire" : "Publication"} signalé par {r.reporter_name}, {ago(r.created_at)} : {r.reason}
                </p>
              </div>
              <Space>
                <Button danger onClick={() => resolve(r, true)}>
                  Masquer
                </Button>
                <Button onClick={() => resolve(r, false)}>Classer</Button>
              </Space>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
