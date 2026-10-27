// Une publication du fil : auteur, type, texte, photos, personnes identifiées,
// sondage, réactions et commentaires. Menu : modifier, épingler, masquer, signaler, supprimer.

import { MoreOutlined } from "@ant-design/icons";
import { App, Button, Dropdown, Image, Input, Modal, Popconfirm } from "antd";
import { useState } from "react";
import { Link } from "react-router";
import { Avatar } from "../../../components/Person";
import { api } from "../../../lib/api";
import type { Post } from "../../../types";
import { LIFE_EVENTS, REACTIONS, ago } from "../format";
import { Comments } from "./Comments";

export function PostCard({ post, onChange, onRemove }: { post: Post; onChange: (p: Post) => void; onRemove: () => void }) {
  const { message } = App.useApp();
  const [showComments, setShowComments] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(post.text);
  const [reporting, setReporting] = useState(false);
  const [reason, setReason] = useState("");

  const label =
    post.kind === "announcement"
      ? "Annonce du bureau"
      : post.kind === "life_event"
        ? LIFE_EVENTS[post.life_event ?? "other"]
        : post.kind === "poll"
          ? "Sondage"
          : null;

  const react = async (key: string) => {
    const removing = post.my_reaction === key;
    await api(`/posts/${post.id}/reaction`, removing ? { method: "DELETE" } : { method: "PUT", body: { emoji: key } });
    const reactions = { ...post.reactions };
    if (post.my_reaction) reactions[post.my_reaction] = Math.max(0, (reactions[post.my_reaction] ?? 1) - 1);
    if (!removing) reactions[key] = (reactions[key] ?? 0) + 1;
    onChange({ ...post, reactions, my_reaction: removing ? null : key });
  };

  const vote = async (optionId: string) => {
    onChange(await api<Post>(`/posts/${post.id}/vote`, { method: "POST", body: { option_id: optionId } }));
  };

  const patch = async (body: object) => {
    onChange(await api<Post>(`/posts/${post.id}`, { method: "PATCH", body }));
  };

  const report = async () => {
    await api("/reports", { method: "POST", body: { post_id: post.id, reason } });
    setReporting(false);
    setReason("");
    message.success("Signalement envoyé à la modération.");
  };

  const totalVotes = post.poll?.reduce((sum, o) => sum + o.votes, 0) ?? 0;
  const menu = [
    ...(post.can_edit ? [{ key: "edit", label: "Modifier le texte" }] : []),
    ...(post.can_moderate ? [{ key: "pin", label: post.pinned ? "Désépingler" : "Épingler en haut du fil" }] : []),
    ...(post.can_moderate ? [{ key: "hide", label: post.hidden ? "Rendre visible" : "Masquer" }] : []),
    ...(!post.can_edit ? [{ key: "report", label: "Signaler" }] : []),
  ];

  return (
    <article className={`post${post.kind === "announcement" ? " post--announcement" : ""}${post.hidden ? " post--hidden" : ""}`}>
      <header className="post__head">
        {post.author.person ? <Avatar person={post.author.person} size={40} /> : <span className="avatar" style={{ width: 40, height: 40 }} />}
        <div style={{ flex: 1, minWidth: 0 }}>
          <span className="pname">
            {post.author.person ? <Link to={`/personnes/${post.author.person.id}`}>{post.author.name}</Link> : post.author.name}
          </span>
          {post.on_behalf_of && <span className="years"> pour {post.on_behalf_of.display_name}</span>}
          <span className="years" style={{ display: "block" }}>
            {label ? `${label}, ` : ""}
            {ago(post.created_at)}
            {post.edited_at ? ", modifié" : ""}
            {post.hidden ? ", masqué" : ""}
          </span>
        </div>
        {(menu.length > 0 || post.can_edit || post.can_moderate) && (
          <Dropdown
            trigger={["click"]}
            menu={{
              items: menu,
              onClick: ({ key }) => {
                if (key === "edit") setEditing(true);
                if (key === "pin") void patch({ pinned: !post.pinned });
                if (key === "hide") void patch({ hidden: !post.hidden });
                if (key === "report") setReporting(true);
              },
            }}
          >
            <Button type="text" icon={<MoreOutlined />} aria-label="Actions" />
          </Dropdown>
        )}
      </header>

      {editing ? (
        <div style={{ marginTop: 10 }}>
          <Input.TextArea value={draft} onChange={(e) => setDraft(e.target.value)} autoSize={{ minRows: 2 }} />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <Button type="primary" size="small" onClick={async () => (await patch({ text: draft }), setEditing(false))}>
              Enregistrer
            </Button>
            <Button size="small" onClick={() => setEditing(false)}>
              Annuler
            </Button>
          </div>
        </div>
      ) : (
        post.text && <p className="post__text">{post.text}</p>
      )}

      {post.media.length > 0 && (
        <div className={`post__media post__media--${Math.min(post.media.length, 3)}`}>
          <Image.PreviewGroup>
            {post.media.map((url) => (
              <Image key={url} src={url} alt="" />
            ))}
          </Image.PreviewGroup>
        </div>
      )}

      {post.persons.length > 0 && (
        <p className="years" style={{ margin: "10px 0 0" }}>
          Avec{" "}
          {post.persons.map((p, i) => (
            <span key={p.id}>
              {i > 0 && ", "}
              <Link to={`/personnes/${p.id}`}>{p.display_name}</Link>
            </span>
          ))}
        </p>
      )}

      {post.poll && (
        <div className="poll">
          {post.poll.map((o) => {
            const share = totalVotes ? Math.round((o.votes / totalVotes) * 100) : 0;
            return (
              <button key={o.id} className={`poll__option${post.my_vote === o.id ? " poll__option--mine" : ""}`} onClick={() => vote(o.id)}>
                <span className="poll__fill" style={{ width: `${share}%` }} />
                <span className="poll__label">{o.label}</span>
                <span className="poll__share">{share} %</span>
              </button>
            );
          })}
          <p className="years" style={{ margin: 0 }}>
            {totalVotes} vote{totalVotes > 1 ? "s" : ""}
          </p>
        </div>
      )}

      <footer className="post__actions">
        {REACTIONS.map((r) => (
          <button
            key={r.key}
            className={`reaction${post.my_reaction === r.key ? " reaction--mine" : ""}`}
            onClick={() => react(r.key)}
            aria-label={r.label}
            title={r.label}
          >
            {r.emoji}
            {post.reactions[r.key] ? <span>{post.reactions[r.key]}</span> : null}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <Button type="text" size="small" onClick={() => setShowComments(!showComments)}>
          {post.comments_count ? `${post.comments_count} commentaire${post.comments_count > 1 ? "s" : ""}` : "Commenter"}
        </Button>
        {(post.can_edit || post.can_moderate) && (
          <Popconfirm title="Supprimer cette publication ?" okText="Supprimer" cancelText="Annuler" onConfirm={async () => (await api(`/posts/${post.id}`, { method: "DELETE" }), onRemove())}>
            <Button type="text" size="small" style={{ color: "var(--muted)" }}>
              Supprimer
            </Button>
          </Popconfirm>
        )}
      </footer>

      {showComments && (
        <Comments postId={post.id} onCount={(n) => onChange({ ...post, comments_count: n })} />
      )}

      <Modal
        open={reporting}
        title="Signaler cette publication"
        okText="Signaler"
        cancelText="Annuler"
        okButtonProps={{ disabled: reason.trim().length < 2 }}
        onOk={report}
        onCancel={() => setReporting(false)}
      >
        <Input.TextArea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Pourquoi ce message pose-t-il problème ?" autoSize={{ minRows: 2 }} />
      </Modal>
    </article>
  );
}
