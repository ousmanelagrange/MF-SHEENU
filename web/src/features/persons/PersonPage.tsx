// Fiche d'une personne : identité à gauche, proches et histoire à droite.
// Les actions affichées dépendent des droits : modifier directement, ou proposer.

import { App, Button, Dropdown, Popconfirm, Space, Spin } from "antd";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ShareInviteModal } from "../../components/ShareInviteModal";
import { api } from "../../lib/api";
import { useFamily } from "../../lib/family";
import type { Kinship, PersonDetail } from "../../types";
import { AddRelativeModal, type Relative } from "./components/AddRelativeModal";
import { DelegatesSection } from "./components/DelegatesSection";
import { GrantTitleModal } from "./components/GrantTitleModal";
import { KinGroup, KinItem } from "./components/KinList";
import { ProfileAside } from "./components/ProfileAside";
import { ContributionHistory } from "../contributions/components/ContributionHistory";
import { Memorial } from "../social/components/Memorial";

const LINK_KIND: Record<string, string> = { biological: "", adoptive: "adoptif", recognized: "reconnu" };
const UNION_KIND: Record<string, string> = { customary: "coutumière", civil: "civile", religious: "religieuse" };

function spouseMeta(rank: number | null, sex: string, kind: string, endReason: string | null) {
  const role = sex === "M" ? "époux" : "épouse";
  const ranked = rank ? `${rank === 1 ? "1er" : `${rank}e`} ${role}`.replace("1er épouse", "1re épouse") : null;
  return [ranked, `union ${UNION_KIND[kind] ?? kind}`, endReason === "divorce" ? "divorcés" : null]
    .filter(Boolean)
    .join(", ");
}

export function PersonPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const { family, isAdmin, canInvite, reload: reloadFamily } = useFamily();
  const [p, setP] = useState<PersonDetail | null>(null);
  const [kin, setKin] = useState<Kinship | null>(null);
  const [adding, setAdding] = useState<Relative | null>(null);
  const [shareText, setShareText] = useState<string | null>(null);
  const [titleOpen, setTitleOpen] = useState(false);

  const load = useCallback(() => {
    void api<PersonDetail>(`/persons/${id}`).then(setP);
    if (family?.person_id && family.person_id !== id) {
      api<Kinship>("/kinship", { query: { to: id } }).then(setKin).catch(() => setKin(null));
    } else setKin(null);
  }, [id, family?.person_id]);

  useEffect(() => {
    setP(null);
    load();
  }, [load]);

  if (!p) return <Spin style={{ margin: 48 }} />;

  const isRoot = family?.root_person_id === p.id;
  const canManage = isAdmin || family?.role === "branch_head";

  const makeRoot = async () => {
    await api("/families/current", { method: "PATCH", body: { root_person_id: p.id } });
    await reloadFamily();
    message.success(`${p.display_name} est désormais l'ancêtre racine.`);
    load();
  };

  const invite = async () => {
    try {
      const r = await api<{ share_text: string }>("/invitations", { method: "POST", body: { person_id: p.id } });
      setShareText(r.share_text);
    } catch (e) {
      message.error((e as Error).message);
    }
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

  const removeLink = async (path: string) => {
    await api(path, { method: "DELETE" });
    message.success("Lien retiré.");
    load();
  };
  const remover = (path: string) => (p.can_edit ? () => removeLink(path) : undefined);

  const actions = (
    <Space wrap style={{ marginTop: 24 }}>
      <Button onClick={() => navigate(`/personnes/${p.id}/modifier`)}>
        {p.can_edit ? "Modifier" : "Proposer une modification"}
      </Button>
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
            if (key === "invite") void invite();
            if (key === "title") setTitleOpen(true);
            if (key === "root") void makeRoot();
          },
        }}
      >
        <Button>Plus</Button>
      </Dropdown>
    </Space>
  );

  return (
    <div className="page">
      <div className="profile">
        <ProfileAside person={p} isRoot={isRoot} kin={kin} mePersonId={family?.person_id ?? null} onChanged={setP}>
          {actions}
        </ProfileAside>

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
                person={r.person}
                meta={[r.person.sex === "F" ? "mère" : r.person.sex === "M" ? "père" : "parent", LINK_KIND[r.kind]]
                  .filter(Boolean)
                  .join(" ")}
                onRemove={remover(`/relations/parent-child/${r.relation_id}`)}
              />
            ))}
          </KinGroup>

          <KinGroup title={p.spouses.length > 1 ? "Conjoints" : "Conjoint"} empty="Aucune union enregistrée.">
            {p.spouses.map((s) => (
              <KinItem
                key={s.union_id}
                person={s.person}
                meta={spouseMeta(s.rank, s.person.sex, s.kind, s.end_reason)}
                onRemove={remover(`/unions/${s.union_id}`)}
              />
            ))}
          </KinGroup>

          <KinGroup title={`Enfants (${p.children.length})`} empty="Aucun enfant enregistré.">
            {p.children.map((r) => (
              <KinItem
                key={r.relation_id}
                person={r.person}
                meta={LINK_KIND[r.kind]}
                onRemove={remover(`/relations/parent-child/${r.relation_id}`)}
              />
            ))}
          </KinGroup>

          {p.siblings.length > 0 && (
            <KinGroup title={`Frères et sœurs (${p.siblings.length})`}>
              {p.siblings.map((s) => (
                <KinItem key={s.id} person={s} />
              ))}
            </KinGroup>
          )}

          {!p.is_living && <Memorial personId={p.id} firstName={p.first_name} />}

          <ContributionHistory personId={p.id} />

          {canManage && !p.has_account && p.can_edit && <DelegatesSection personId={p.id} />}

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
      <ShareInviteModal title={`Inviter ${p.first_name}`} shareText={shareText} onClose={() => setShareText(null)} />
      <GrantTitleModal open={titleOpen} personId={p.id} onClose={() => setTitleOpen(false)} onDone={load} />
    </div>
  );
}
