// Bandeau des stories (photos visibles 24 heures) : ajouter la sienne, regarder celles des autres.

import { PlusOutlined } from "@ant-design/icons";
import { App, Input, Modal, Upload } from "antd";
import { useEffect, useState } from "react";
import { Avatar } from "../../../components/Person";
import { api } from "../../../lib/api";
import type { PersonSummary, StoryGroup } from "../../../types";
import { ago, uploadImage } from "../format";

export function StoriesBar({ me }: { me: PersonSummary | null }) {
  const { message } = App.useApp();
  const [groups, setGroups] = useState<StoryGroup[]>([]);
  const [viewing, setViewing] = useState<{ group: number; index: number } | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [caption, setCaption] = useState("");

  const load = () => void api<StoryGroup[]>("/stories").then(setGroups);
  useEffect(load, []);

  const pick = async (file: File) => {
    try {
      setPending(await uploadImage(file));
    } catch (e) {
      message.error((e as Error).message);
    }
    return false;
  };

  const publish = async () => {
    await api("/stories", { method: "POST", body: { media_url: pending, caption: caption || null } });
    setPending(null);
    setCaption("");
    load();
  };

  const current = viewing ? groups[viewing.group]?.stories[viewing.index] : null;
  const next = () => {
    if (!viewing) return;
    const g = groups[viewing.group];
    if (viewing.index + 1 < g.stories.length) setViewing({ ...viewing, index: viewing.index + 1 });
    else if (viewing.group + 1 < groups.length) setViewing({ group: viewing.group + 1, index: 0 });
    else setViewing(null);
  };

  return (
    <div className="stories">
      <Upload accept="image/*" showUploadList={false} beforeUpload={pick}>
        <button className="story-bubble story-bubble--add" aria-label="Ajouter une story">
          <span className="story-bubble__ring">
            {me ? <Avatar person={me} size={56} /> : null}
            <span className="story-bubble__plus">
              <PlusOutlined />
            </span>
          </span>
          <span className="story-bubble__name">Ma story</span>
        </button>
      </Upload>
      {groups.map((g, gi) => (
        <button key={g.author.user_id} className="story-bubble" onClick={() => setViewing({ group: gi, index: 0 })}>
          <span className="story-bubble__ring story-bubble__ring--new">
            {g.author.person ? <Avatar person={g.author.person} size={56} /> : <span className="avatar" style={{ width: 56, height: 56 }} />}
          </span>
          <span className="story-bubble__name">{g.author.name.split(" ").slice(-2).join(" ")}</span>
        </button>
      ))}

      <Modal open={!!current} onCancel={() => setViewing(null)} footer={null} width={420} centered styles={{ body: { padding: 0 } }} closable>
        {current && viewing && (
          <div className="story-view" onClick={next}>
            <img src={current.media_url} alt="" />
            <div className="story-view__meta">
              <strong>{groups[viewing.group].author.name}</strong> {ago(current.created_at)}
              {current.caption && <p>{current.caption}</p>}
            </div>
          </div>
        )}
      </Modal>

      <Modal open={!!pending} title="Nouvelle story" okText="Publier pour 24 heures" cancelText="Annuler" onOk={publish} onCancel={() => setPending(null)}>
        {pending && <img src={pending} alt="" style={{ width: "100%", borderRadius: 8 }} />}
        <Input value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="Légende (facultatif)" style={{ marginTop: 12 }} maxLength={300} />
      </Modal>
    </div>
  );
}
