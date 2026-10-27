// Cloche des notifications : nombre de non lues, liste au clic, lien vers l'élément concerné.
// La liste est relue chaque minute et quand on revient sur l'onglet.

import { BellOutlined } from "@ant-design/icons";
import { Badge, Button, Empty, Popover } from "antd";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../../lib/api";
import { useFamily } from "../../lib/family";
import { ago } from "../social/format";

type Item = { id: string; kind: string; title: string; body: string | null; link: string | null; read: boolean; created_at: string };
type Page = { items: Item[]; unread: number };

export function NotificationsBell({ tone = "dark" }: { tone?: "dark" | "light" }) {
  const { family } = useFamily();
  const navigate = useNavigate();
  const [page, setPage] = useState<Page>({ items: [], unread: 0 });
  const [open, setOpen] = useState(false);

  const load = useCallback(() => {
    if (family) void api<Page>("/notifications").then(setPage).catch(() => undefined);
  }, [family]);

  useEffect(() => {
    load();
    const id = window.setInterval(load, 60_000);
    window.addEventListener("focus", load);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("focus", load);
    };
  }, [load]);

  const read = async (ids?: string[]) => {
    await api("/notifications/read", { method: "POST", body: { ids: ids ?? null } });
    load();
  };

  const openItem = (n: Item) => {
    setOpen(false);
    if (!n.read) void read([n.id]);
    if (n.link) navigate(n.link);
  };

  const list = (
    <div className="notif">
      <div className="notif__head">
        <strong>Notifications</strong>
        {page.unread > 0 && (
          <Button type="link" size="small" onClick={() => read()}>
            Tout marquer comme lu
          </Button>
        )}
      </div>
      {page.items.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Rien de nouveau." />
      ) : (
        <ul>
          {page.items.map((n) => (
            <li key={n.id}>
              <button className={`notif__item${n.read ? "" : " is-unread"}`} onClick={() => openItem(n)}>
                <span className="notif__title">{n.title}</span>
                {n.body && <span className="notif__body">{n.body}</span>}
                <span className="notif__when">{ago(n.created_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  return (
    <Popover content={list} trigger="click" open={open} onOpenChange={setOpen} placement="bottomLeft" arrow={false}>
      <button className={`bell bell--${tone}`} aria-label={`Notifications, ${page.unread} non lues`}>
        <Badge count={page.unread} size="small" color="#9c7428" offset={[2, -2]}>
          <BellOutlined />
        </Badge>
      </button>
    </Popover>
  );
}
