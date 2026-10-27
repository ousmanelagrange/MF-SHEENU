// Un album : grille de photos, ajout de plusieurs photos d'un coup, visionneuse où l'on
// reconnaît les personnes présentes.

import { PlusOutlined } from "@ant-design/icons";
import { App, Button, InputNumber, Input, Modal, Popconfirm, Spin, Upload } from "antd";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api } from "../../lib/api";
import { count } from "../../lib/text";
import type { Album, AlbumPhoto } from "../../types";
import { uploadImage } from "../social/format";
import { PersonsField } from "./components/PersonsField";

export function AlbumPage() {
  const { id } = useParams();
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [album, setAlbum] = useState<Album | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [adding, setAdding] = useState(0);

  const load = useCallback(() => void api<Album>(`/albums/${id}`).then(setAlbum), [id]);
  useEffect(load, [load]);

  const add = async (file: File) => {
    setAdding((n) => n + 1);
    try {
      const url = await uploadImage(file);
      await api(`/albums/${id}/photos`, { method: "POST", body: { url } });
      load();
    } catch (e) {
      message.error(`${file.name} : ${(e as Error).message}`);
    } finally {
      setAdding((n) => n - 1);
    }
    return false;
  };

  if (!album) return <Spin style={{ display: "block", margin: 60 }} />;
  const photo = open !== null ? album.photos[open] : null;

  return (
    <div className="page">
      <p className="crumb">
        <Link to="/memoire/albums">Albums</Link>
      </p>
      <header className="page__head">
        <div>
          <h1 className="page__title">{album.title}</h1>
          <p className="page__lead">{[album.year, album.photos.length ? count(album.photos.length, "photo") : "aucune photo"].filter(Boolean).join(", ")}</p>
          {album.description && <p className="bio">{album.description}</p>}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Upload accept="image/*" multiple showUploadList={false} beforeUpload={add}>
            <Button type="primary" icon={<PlusOutlined />} loading={adding > 0}>
              Ajouter des photos
            </Button>
          </Upload>
          {album.can_edit && (
            <Popconfirm
              title="Supprimer l'album et ses photos ?"
              okText="Supprimer"
              cancelText="Annuler"
              onConfirm={async () => {
                await api(`/albums/${album.id}`, { method: "DELETE" });
                navigate("/memoire/albums");
              }}
            >
              <Button type="text" danger>
                Supprimer
              </Button>
            </Popconfirm>
          )}
        </div>
      </header>

      <div className="photo-grid">
        {album.photos.map((p, i) => (
          <button key={p.id} className="photo-grid__item" onClick={() => setOpen(i)} aria-label={p.caption ?? "Photo"}>
            <img src={p.url} alt={p.caption ?? ""} loading="lazy" />
            {p.persons.length > 0 && <span className="photo-grid__count">{p.persons.length}</span>}
          </button>
        ))}
      </div>

      <Modal open={!!photo} onCancel={() => setOpen(null)} footer={null} width={980} centered destroyOnHidden>
        {photo && open !== null && (
          <PhotoViewer
            key={photo.id}
            photo={photo}
            onPrev={open > 0 ? () => setOpen(open - 1) : undefined}
            onNext={open < album.photos.length - 1 ? () => setOpen(open + 1) : undefined}
            onSaved={(p) => setAlbum({ ...album, photos: album.photos.map((x) => (x.id === p.id ? p : x)) })}
            onDeleted={() => {
              setOpen(null);
              load();
            }}
          />
        )}
      </Modal>
    </div>
  );
}

function PhotoViewer({
  photo,
  onPrev,
  onNext,
  onSaved,
  onDeleted,
}: {
  photo: AlbumPhoto;
  onPrev?: () => void;
  onNext?: () => void;
  onSaved: (p: AlbumPhoto) => void;
  onDeleted: () => void;
}) {
  const [caption, setCaption] = useState(photo.caption ?? "");
  const [year, setYear] = useState<number | null>(photo.year);

  const patch = async (body: object) => onSaved(await api<AlbumPhoto>(`/album-photos/${photo.id}`, { method: "PATCH", body }));

  return (
    <div className="viewer">
      <div className="viewer__image">
        <img src={photo.url} alt={photo.caption ?? ""} />
        <div className="viewer__nav">
          <Button disabled={!onPrev} onClick={onPrev}>
            Précédente
          </Button>
          <Button disabled={!onNext} onClick={onNext}>
            Suivante
          </Button>
        </div>
      </div>
      <aside className="viewer__side">
        {photo.can_edit ? (
          <>
            <label className="field-label">Légende</label>
            <Input.TextArea value={caption} onChange={(e) => setCaption(e.target.value)} onBlur={() => caption !== (photo.caption ?? "") && patch({ caption: caption || null })} autoSize />
            <label className="field-label">Année</label>
            <InputNumber value={year} min={1000} max={2100} onChange={setYear} onBlur={() => year !== photo.year && patch({ year })} style={{ width: 120 }} />
          </>
        ) : (
          <>
            {photo.caption && <p className="bio">{photo.caption}</p>}
            {photo.year && <p className="years">{photo.year}</p>}
          </>
        )}
        <label className="field-label">Sur la photo</label>
        <PersonsField
          value={photo.persons}
          onChange={(persons) => patch({ person_ids: persons.map((p) => p.id) })}
          placeholder="Reconnaître quelqu'un"
        />
        <p className="years" style={{ marginTop: 16 }}>
          Ajoutée par {photo.added_by}
        </p>
        {photo.can_edit && (
          <Popconfirm
            title="Retirer cette photo ?"
            okText="Retirer"
            cancelText="Annuler"
            onConfirm={async () => {
              await api(`/album-photos/${photo.id}`, { method: "DELETE" });
              onDeleted();
            }}
          >
            <Button type="text" danger style={{ paddingLeft: 0 }}>
              Retirer la photo
            </Button>
          </Popconfirm>
        )}
      </aside>
    </div>
  );
}
