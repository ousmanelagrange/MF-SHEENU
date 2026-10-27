// Zone de rédaction du fil : texte, photos, personnes identifiées ; selon le type,
// annonce de vie ou sondage. Le bureau et le secrétaire publient aussi des annonces officielles.

import { CloseOutlined, PictureOutlined, UserAddOutlined } from "@ant-design/icons";
import { App, Button, Input, Segmented, Select, Tag, Upload } from "antd";
import { useState } from "react";
import { Avatar, PersonPicker } from "../../../components/Person";
import { api } from "../../../lib/api";
import { useFamily } from "../../../lib/family";
import type { PersonSummary, Post } from "../../../types";
import { LIFE_EVENTS, uploadImage } from "../format";

type Kind = Post["kind"];

export function Composer({ me, onPosted }: { me: PersonSummary | null; onPosted: (p: Post) => void }) {
  const { message } = App.useApp();
  const { family } = useFamily();
  const canAnnounce = family?.role === "admin" || family?.role === "secretary";
  const [kind, setKind] = useState<Kind>("post");
  const [text, setText] = useState("");
  const [media, setMedia] = useState<string[]>([]);
  const [persons, setPersons] = useState<PersonSummary[]>([]);
  const [tagging, setTagging] = useState(false);
  const [lifeEvent, setLifeEvent] = useState("birth");
  const [options, setOptions] = useState<string[]>(["", ""]);
  const [busy, setBusy] = useState(false);

  const reset = () => {
    setKind("post");
    setText("");
    setMedia([]);
    setPersons([]);
    setTagging(false);
    setOptions(["", ""]);
  };

  const publish = async () => {
    setBusy(true);
    try {
      const post = await api<Post>("/posts", {
        method: "POST",
        body: {
          kind,
          text,
          media,
          person_ids: persons.map((p) => p.id),
          life_event: kind === "life_event" ? lifeEvent : null,
          poll_options: kind === "poll" ? options : [],
        },
      });
      onPosted(post);
      reset();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const addPhoto = async (file: File) => {
    try {
      const url = await uploadImage(file);
      setMedia((m) => [...m, url]);
    } catch (e) {
      message.error((e as Error).message);
    }
    return false;
  };

  return (
    <div className="composer">
      <div style={{ display: "flex", gap: 12 }}>
        {me && <Avatar person={me} size={40} />}
        <div style={{ flex: 1, minWidth: 0 }}>
          <Segmented
            size="small"
            value={kind}
            onChange={(v) => setKind(v as Kind)}
            options={[
              { label: "Publication", value: "post" },
              { label: "Annonce de vie", value: "life_event" },
              { label: "Sondage", value: "poll" },
              ...(canAnnounce ? [{ label: "Annonce officielle", value: "announcement" }] : []),
            ]}
            style={{ marginBottom: 10 }}
          />
          {kind === "life_event" && (
            <Select
              value={lifeEvent}
              onChange={setLifeEvent}
              style={{ width: 200, marginBottom: 10, display: "block" }}
              options={Object.entries(LIFE_EVENTS).map(([value, label]) => ({ value, label }))}
            />
          )}
          <Input.TextArea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={
              kind === "poll"
                ? "Votre question"
                : kind === "announcement"
                  ? "Annonce du bureau à toute la famille"
                  : "Une nouvelle à partager avec la famille ?"
            }
            autoSize={{ minRows: 2, maxRows: 10 }}
            variant="borderless"
            style={{ padding: 0, fontSize: 16 }}
          />
          {kind === "poll" && (
            <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
              {options.map((o, i) => (
                <Input
                  key={i}
                  value={o}
                  placeholder={`Choix ${i + 1}`}
                  onChange={(e) => setOptions(options.map((x, j) => (j === i ? e.target.value : x)))}
                />
              ))}
              {options.length < 10 && (
                <Button type="dashed" size="small" onClick={() => setOptions([...options, ""])}>
                  Ajouter un choix
                </Button>
              )}
            </div>
          )}
          {media.length > 0 && (
            <div className="composer__media">
              {media.map((url) => (
                <span key={url}>
                  <img src={url} alt="" />
                  <button aria-label="Retirer la photo" onClick={() => setMedia(media.filter((m) => m !== url))}>
                    <CloseOutlined />
                  </button>
                </span>
              ))}
            </div>
          )}
          {(tagging || persons.length > 0 || kind === "life_event") && (
            <div style={{ marginTop: 8 }}>
              {persons.map((p) => (
                <Tag key={p.id} closable onClose={() => setPersons(persons.filter((x) => x.id !== p.id))}>
                  {p.display_name}
                </Tag>
              ))}
              <PersonPicker
                placeholder={kind === "life_event" ? "Personne concernée" : "Identifier quelqu'un"}
                style={{ marginTop: 6 }}
                value={null}
                onChange={(_, person) => person && !persons.some((x) => x.id === person.id) && setPersons([...persons, person])}
              />
            </div>
          )}
          <div className="composer__bar">
            <Upload accept="image/*" showUploadList={false} beforeUpload={addPhoto} multiple>
              <Button type="text" icon={<PictureOutlined />}>
                Photo
              </Button>
            </Upload>
            {!tagging && kind !== "life_event" && (
              <Button type="text" icon={<UserAddOutlined />} onClick={() => setTagging(true)}>
                Identifier
              </Button>
            )}
            <div style={{ flex: 1 }} />
            <Button type="primary" loading={busy} disabled={!text.trim() && media.length === 0} onClick={publish}>
              Publier
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
