// Colonne d'identité d'une fiche : portrait (avec changement de photo), nom, titres,
// lien de parenté avec l'utilisateur, faits (naissance, décès, génération, lieux, contact).

import { CameraOutlined } from "@ant-design/icons";
import { App, Button, Space, Upload } from "antd";
import { Link } from "react-router";
import { Avatar, TitleBadges, lifeSpan } from "../../../components/Person";
import { api } from "../../../lib/api";
import type { Kinship, PersonDetail } from "../../../types";

const VISIBILITY: Record<string, string> = {
  family: "toute la famille",
  branch: "sa branche",
  board: "le bureau",
  private: "personne",
};

function formatDate(d: string | null, year: number | null) {
  if (d) return new Date(d).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
  return year ? String(year) : null;
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  if (!children) return null;
  return (
    <>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </>
  );
}

export function ProfileAside({
  person: p,
  isRoot,
  kin,
  mePersonId,
  onChanged,
  children,
}: {
  person: PersonDetail;
  isRoot: boolean;
  kin: Kinship | null;
  mePersonId: string | null;
  onChanged: (p: PersonDetail) => void;
  children?: React.ReactNode;
}) {
  const { message } = App.useApp();

  const uploadPhoto = async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    try {
      onChanged(await api<PersonDetail>(`/persons/${p.id}/photo`, { method: "POST", form }));
      message.success("Photo enregistrée.");
    } catch (e) {
      message.error((e as Error).message);
    }
    return false; // empêche le téléversement automatique d'Ant Design
  };

  const birth = formatDate(p.birth_date, p.birth_year);
  const death = formatDate(p.death_date, p.death_year);
  const place = (value: string | null, where: string | null) => (value ? `${value}${where ? `, ${where}` : ""}` : null);

  return (
    <aside className="profile__id">
      <div style={{ position: "relative", width: 140 }}>
        <Avatar person={p} size={140} />
        {p.can_edit && (
          <Upload accept="image/*" showUploadList={false} beforeUpload={uploadPhoto}>
            <Button
              shape="circle"
              icon={<CameraOutlined />}
              aria-label="Changer la photo"
              style={{ position: "absolute", right: 0, bottom: 4 }}
            />
          </Upload>
        )}
      </div>
      <h1 className="profile__name">{p.display_name}</h1>
      <p className="profile__alt">
        {[p.traditional_name, p.nickname && `dit ${p.nickname}`].filter(Boolean).join(", ") || lifeSpan(p)}
      </p>
      <Space wrap size={6}>
        <TitleBadges titles={p.titles} max={6} />
        {isRoot && (
          <span className="title-badge" style={{ color: "var(--indigo-700)", background: "var(--indigo-100)" }}>
            Ancêtre racine
          </span>
        )}
      </Space>
      {kin?.label && (
        <p style={{ marginTop: 16 }}>
          Pour vous : <span className="pname">{kin.label}</span>{" "}
          <Link to={`/parente?de=${mePersonId}&a=${p.id}`}>voir le chemin</Link>
        </p>
      )}
      <dl className="facts">
        <Fact label="Naissance">{place(birth, p.birth_place)}</Fact>
        {!p.is_living && <Fact label="Décès">{place(death ?? "date inconnue", p.death_place)}</Fact>}
        <Fact label="Génération">{p.generation}</Fact>
        <Fact label="Village">{p.village}</Fact>
        <Fact label="Pays">{p.country}</Fact>
        <Fact label="Téléphone">{p.phone && <a href={`tel:${p.phone}`}>{p.phone}</a>}</Fact>
        <Fact label="E-mail">{p.email}</Fact>
        {p.can_edit && (p.phone || p.email) && (
          <Fact label="Coordonnées">visibles par {VISIBILITY[p.contact_visibility]}</Fact>
        )}
      </dl>
      {children}
    </aside>
  );
}
