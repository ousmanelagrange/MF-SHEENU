import { CameraOutlined } from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  DatePicker,
  Dropdown,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Upload,
} from "antd";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api } from "../api";
import { Avatar, PersonLine, PersonPicker, TitleBadges, lifeSpan } from "../components/Person";
import { useFamily } from "../family";
import type { Kinship, PersonDetail, Title } from "../types";

const KIND: Record<string, string> = {
  biological: "",
  adoptive: "adoptif",
  recognized: "reconnu",
  customary: "coutumière",
  civil: "civile",
  religious: "religieuse",
};
const VIS: Record<string, string> = {
  family: "toute la famille",
  branch: "sa branche",
  board: "le bureau",
  private: "personne",
};

function formatDate(d: string | null, y: number | null) {
  if (d) return new Date(d).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
  return y ? String(y) : null;
}

type Relative = "child" | "parent" | "spouse";

export function PersonPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const { family, isAdmin, canInvite, reload: reloadFamily } = useFamily();
  const [p, setP] = useState<PersonDetail | null>(null);
  const [kin, setKin] = useState<Kinship | null>(null);
  const [adding, setAdding] = useState<Relative | null>(null);
  const [invite, setInvite] = useState<{ link: string; share_text: string } | null>(null);
  const [titleOpen, setTitleOpen] = useState(false);

  const load = useCallback(() => {
    api<PersonDetail>(`/persons/${id}`).then(setP);
    if (family?.person_id && family.person_id !== id) {
      api<Kinship>("/kinship", { query: { to: id } }).then(setKin).catch(() => setKin(null));
    } else setKin(null);
  }, [id, family?.person_id]);

  useEffect(() => {
    setP(null);
    load();
  }, [load]);

  if (!p) return <Spin style={{ margin: 48 }} />;

  const upload = async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    try {
      setP(await api<PersonDetail>(`/persons/${p.id}/photo`, { method: "POST", form }));
      message.success("Photo enregistrée.");
    } catch (e) {
      message.error((e as Error).message);
    }
    return false;
  };

  const makeRoot = async () => {
    await api("/families/current", { method: "PATCH", body: { root_person_id: p.id } });
    await reloadFamily();
    message.success(`${p.display_name} est désormais l'ancêtre racine.`);
    load();
  };

  const archive = async () => {
    try {
      await api(`/persons/${p.id}`, { method: "DELETE" });
      message.success("Fiche archivée.");
      navigate("/personnes");
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  const createInvite = async () => {
    try {
      setInvite(await api("/invitations", { method: "POST", body: { person_id: p.id } }));
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  const removeLink = async (path: string) => {
    await api(path, { method: "DELETE" });
    message.success("Lien supprimé.");
    load();
  };

  const birth = formatDate(p.birth_date, p.birth_year);
  const death = formatDate(p.death_date, p.death_year);
  const isRoot = family?.root_person_id === p.id;

  return (
    <div className="page">
      <div className="profile">
        <aside className="profile__id">
          <div style={{ position: "relative", width: 140 }}>
            <Avatar person={p} size={140} />
            {p.can_edit && (
              <Upload accept="image/*" showUploadList={false} beforeUpload={upload}>
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
              <Link to={`/parente?de=${family?.person_id}&a=${p.id}`}>voir le chemin</Link>
            </p>
          )}
          <dl className="facts">
            {birth && (
              <>
                <dt>Naissance</dt>
                <dd>
                  {birth}
                  {p.birth_place ? `, ${p.birth_place}` : ""}
                </dd>
              </>
            )}
            {!p.is_living && (
              <>
                <dt>Décès</dt>
                <dd>
                  {death ?? "date inconnue"}
                  {p.death_place ? `, ${p.death_place}` : ""}
                </dd>
              </>
            )}
            {p.generation && (
              <>
                <dt>Génération</dt>
                <dd>{p.generation}</dd>
              </>
            )}
            {p.village && (
              <>
                <dt>Village</dt>
                <dd>{p.village}</dd>
              </>
            )}
            {p.country && (
              <>
                <dt>Pays</dt>
                <dd>{p.country}</dd>
              </>
            )}
            {p.phone && (
              <>
                <dt>Téléphone</dt>
                <dd>
                  <a href={`tel:${p.phone}`}>{p.phone}</a>
                </dd>
              </>
            )}
            {p.email && (
              <>
                <dt>E-mail</dt>
                <dd>{p.email}</dd>
              </>
            )}
            {p.can_edit && (p.phone || p.email) && (
              <>
                <dt>Coordonnées</dt>
                <dd>visibles par {VIS[p.contact_visibility]}</dd>
              </>
            )}
          </dl>

          <Space wrap style={{ marginTop: 24 }}>
            {p.can_edit && <Button onClick={() => navigate(`/personnes/${p.id}/modifier`)}>Modifier</Button>}
            {p.can_edit && (
              <Dropdown
                menu={{
                  items: [
                    { key: "child", label: "Un enfant" },
                    { key: "spouse", label: "Un conjoint" },
                    { key: "parent", label: "Un parent" },
                  ],
                  onClick: ({ key }) => setAdding(key as Relative),
                }}
              >
                <Button type="primary">Ajouter</Button>
              </Dropdown>
            )}
            <Dropdown
              menu={{
                items: [
                  { key: "tree", label: "Centrer l'arbre ici" },
                  ...(canInvite && !p.has_account && p.is_living ? [{ key: "invite", label: "Inviter sur Sheenu" }] : []),
                  ...(isAdmin ? [{ key: "title", label: "Attribuer un titre" }] : []),
                  ...(isAdmin && !isRoot ? [{ key: "root", label: "Définir comme racine" }] : []),
                ],
                onClick: ({ key }) => {
                  if (key === "tree") navigate(`/arbre?centre=${p.id}`);
                  if (key === "invite") void createInvite();
                  if (key === "title") setTitleOpen(true);
                  if (key === "root") void makeRoot();
                },
              }}
            >
              <Button>Plus</Button>
            </Dropdown>
          </Space>
        </aside>

        <div>
          {p.biography && (
            <section className="kin-group">
              <h2>Histoire</h2>
              <p className="bio">{p.biography}</p>
            </section>
          )}

          <KinGroup title="Parents" empty="Aucun parent rattaché.">
            {p.parents.map((r) => (
              <KinItem
                key={r.relation_id}
                link={r}
                meta={[r.person.sex === "F" ? "mère" : r.person.sex === "M" ? "père" : "parent", KIND[r.kind]]
                  .filter(Boolean)
                  .join(" ")}
                onRemove={p.can_edit ? () => removeLink(`/relations/parent-child/${r.relation_id}`) : undefined}
              />
            ))}
          </KinGroup>

          <KinGroup title={p.spouses.length > 1 ? "Conjoints" : "Conjoint"} empty="Aucune union enregistrée.">
            {p.spouses.map((s) => (
              <KinItem
                key={s.union_id}
                link={s}
                meta={[
                  s.rank ? (s.rank === 1 ? "1re épouse" : `${s.rank}e épouse`).replace("épouse", s.person.sex === "M" ? "époux" : "épouse") : null,
                  `union ${KIND[s.kind]}`,
                  s.end_reason === "divorce" ? "divorcés" : null,
                ]
                  .filter(Boolean)
                  .join(", ")}
                onRemove={p.can_edit ? () => removeLink(`/unions/${s.union_id}`) : undefined}
              />
            ))}
          </KinGroup>

          <KinGroup title={`Enfants (${p.children.length})`} empty="Aucun enfant enregistré.">
            {p.children.map((r) => (
              <KinItem
                key={r.relation_id}
                link={r}
                meta={KIND[r.kind]}
                onRemove={p.can_edit ? () => removeLink(`/relations/parent-child/${r.relation_id}`) : undefined}
              />
            ))}
          </KinGroup>

          {p.siblings.length > 0 && (
            <KinGroup title={`Frères et sœurs (${p.siblings.length})`}>
              {p.siblings.map((s) => (
                <li key={s.id}>
                  <Link to={`/personnes/${s.id}`}>
                    <PersonLine person={s} link={false} />
                  </Link>
                </li>
              ))}
            </KinGroup>
          )}

          {p.can_edit && !p.has_account && !isRoot && (
            <div style={{ marginTop: 40 }}>
              <Popconfirm
                title="Archiver cette fiche ?"
                description="Elle disparaît de l'arbre mais reste dans l'historique."
                okText="Archiver"
                cancelText="Annuler"
                okButtonProps={{ danger: true }}
                onConfirm={archive}
              >
                <Button type="text" danger>
                  Archiver la fiche
                </Button>
              </Popconfirm>
            </div>
          )}
        </div>
      </div>

      <AddRelativeModal person={p} kind={adding} onClose={() => setAdding(null)} onDone={load} />

      <Modal open={!!invite} onCancel={() => setInvite(null)} footer={null} title={`Inviter ${p.first_name}`}>
        {invite && (
          <>
            <p style={{ color: "var(--muted)", marginTop: 0 }}>
              Ce lien est personnel, valable 7 jours et utilisable une seule fois.
            </p>
            <Input.TextArea value={invite.share_text} autoSize readOnly />
            <Space style={{ marginTop: 16 }} wrap>
              <Button
                type="primary"
                href={`https://wa.me/?text=${encodeURIComponent(invite.share_text)}`}
                target="_blank"
                rel="noreferrer"
              >
                Partager sur WhatsApp
              </Button>
              <Button
                onClick={() => {
                  void navigator.clipboard.writeText(invite.share_text);
                  message.success("Message copié.");
                }}
              >
                Copier le message
              </Button>
            </Space>
          </>
        )}
      </Modal>

      <GrantTitleModal open={titleOpen} personId={p.id} onClose={() => setTitleOpen(false)} onDone={load} />
    </div>
  );
}

function KinGroup({ title, empty, children }: { title: string; empty?: string; children: React.ReactNode }) {
  const list = Array.isArray(children) ? children : [children];
  return (
    <section className="kin-group">
      <h2>{title}</h2>
      {list.length === 0 && empty ? (
        <p style={{ color: "var(--muted)", margin: 0 }}>{empty}</p>
      ) : (
        <ul className="kin-list">{children}</ul>
      )}
    </section>
  );
}

function KinItem({
  link,
  meta,
  onRemove,
}: {
  link: { person: PersonDetail["parents"][number]["person"] };
  meta?: string;
  onRemove?: () => void;
}) {
  return (
    <li style={{ display: "flex", alignItems: "center" }}>
      <Link to={`/personnes/${link.person.id}`} style={{ flex: 1 }}>
        <PersonLine person={link.person} link={false} />
        <span className="kin-meta">{meta}</span>
      </Link>
      {onRemove && (
        <Popconfirm title="Supprimer ce lien ?" okText="Supprimer" cancelText="Annuler" onConfirm={onRemove}>
          <Button type="text" size="small" aria-label="Supprimer le lien" style={{ color: "var(--muted)" }}>
            Retirer
          </Button>
        </Popconfirm>
      )}
    </li>
  );
}

function AddRelativeModal({
  person,
  kind,
  onClose,
  onDone,
}: {
  person: PersonDetail;
  kind: Relative | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [existing, setExisting] = useState<string | undefined>();
  const [linkKind, setLinkKind] = useState("biological");
  const [unionKind, setUnionKind] = useState("customary");
  const [rank, setRank] = useState<number | undefined>();
  const [error, setError] = useState<string | null>(null);
  const label = kind === "child" ? "un enfant" : kind === "parent" ? "un parent" : "un conjoint";

  const newPerson = () => {
    const q = new URLSearchParams();
    if (kind === "child") {
      q.set("parent", person.id);
      if (person.spouses.length === 1) q.set("parent2", person.spouses[0].person.id);
    }
    if (kind === "spouse") q.set("conjoint", person.id);
    if (kind === "parent") q.set("enfant", person.id);
    onClose();
    navigate(`/personnes/nouvelle?${q}`);
  };

  const linkExisting = async () => {
    if (!existing) return;
    setError(null);
    try {
      if (kind === "spouse") {
        await api("/unions", {
          method: "POST",
          body: { person_a_id: person.id, person_b_id: existing, kind: unionKind, rank },
        });
      } else {
        await api("/relations/parent-child", {
          method: "POST",
          body:
            kind === "child"
              ? { parent_id: person.id, child_id: existing, kind: linkKind }
              : { parent_id: existing, child_id: person.id, kind: linkKind },
        });
      }
      message.success("Lien enregistré.");
      setExisting(undefined);
      onClose();
      onDone();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <Modal open={!!kind} onCancel={onClose} footer={null} title={`Ajouter ${label} à ${person.first_name}`} destroyOnHidden>
      <p style={{ marginTop: 0 }}>Cette personne n'est pas encore dans l'arbre ?</p>
      <Button type="primary" onClick={newPerson}>
        Créer sa fiche
      </Button>
      <p style={{ margin: "28px 0 8px" }}>Elle a déjà une fiche ? Relier une personne existante :</p>
      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 12 }} />}
      <Space direction="vertical" style={{ width: "100%" }}>
        <PersonPicker value={existing} onChange={(v) => setExisting(v)} exclude={[person.id]} />
        {kind !== "spouse" ? (
          <Select
            value={linkKind}
            onChange={setLinkKind}
            options={[
              { value: "biological", label: "Filiation biologique" },
              { value: "adoptive", label: "Adoption" },
              { value: "recognized", label: "Reconnaissance coutumière" },
            ]}
          />
        ) : (
          <Space.Compact style={{ width: "100%" }}>
            <Select
              value={unionKind}
              onChange={setUnionKind}
              style={{ width: "60%" }}
              options={[
                { value: "customary", label: "Union coutumière" },
                { value: "civil", label: "Mariage civil" },
                { value: "religious", label: "Mariage religieux" },
              ]}
            />
            <Select
              value={rank}
              onChange={setRank}
              allowClear
              placeholder="Rang"
              style={{ width: "40%" }}
              options={[1, 2, 3, 4, 5, 6].map((r) => ({ value: r, label: r === 1 ? "1re épouse" : `${r}e épouse` }))}
            />
          </Space.Compact>
        )}
        <Button onClick={linkExisting} disabled={!existing}>
          Relier
        </Button>
      </Space>
    </Modal>
  );
}

function GrantTitleModal({
  open,
  personId,
  onClose,
  onDone,
}: {
  open: boolean;
  personId: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const { message } = App.useApp();
  const [titles, setTitles] = useState<Title[]>([]);
  useEffect(() => {
    if (open) api<Title[]>("/titles").then(setTitles);
  }, [open]);
  const submit = async (v: { title_id: string; conferred_by?: string; conferred_on?: { format: (f: string) => string } }) => {
    try {
      await api(`/persons/${personId}/titles`, {
        method: "POST",
        body: { ...v, conferred_on: v.conferred_on?.format("YYYY-MM-DD") },
      });
      message.success("Titre attribué.");
      onClose();
      onDone();
    } catch (e) {
      message.error((e as Error).message);
    }
  };
  return (
    <Modal open={open} onCancel={onClose} footer={null} title="Attribuer un titre" destroyOnHidden>
      {titles.length === 0 ? (
        <p>
          Aucun titre n'est encore défini. <Link to="/titres">Créer les titres de la famille</Link>
        </p>
      ) : (
        <Form layout="vertical" requiredMark={false} onFinish={submit}>
          <Form.Item name="title_id" label="Titre" rules={[{ required: true }]}>
            <Select options={titles.map((t) => ({ value: t.id, label: t.name }))} />
          </Form.Item>
          <Form.Item name="conferred_by" label="Conféré par" extra="Chefferie, palais royal, autorité traditionnelle">
            <Input />
          </Form.Item>
          <Form.Item name="conferred_on" label="Date">
            <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            Attribuer
          </Button>
        </Form>
      )}
    </Modal>
  );
}
