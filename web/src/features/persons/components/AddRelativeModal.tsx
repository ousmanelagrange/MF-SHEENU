// Ajouter un proche à une fiche : créer une nouvelle fiche, ou relier une personne existante.
// Hors périmètre, la liaison devient une proposition à valider.

import { Alert, App, Button, Modal, Select, Space } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router";
import { PersonPicker } from "../../../components/Person";
import { api } from "../../../lib/api";
import type { PersonDetail } from "../../../types";
import { useSubmitOrPropose } from "../../proposals/useSubmitOrPropose";

export type Relative = "child" | "parent" | "spouse";

const LABEL: Record<Relative, string> = { child: "un enfant", parent: "un parent", spouse: "un conjoint" };

export function AddRelativeModal({
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
  const { run } = useSubmitOrPropose();
  const [existing, setExisting] = useState<string | undefined>();
  const [linkKind, setLinkKind] = useState("biological");
  const [unionKind, setUnionKind] = useState("customary");
  const [rank, setRank] = useState<number | undefined>();
  const [error, setError] = useState<string | null>(null);

  // Nouvelle fiche : le formulaire reçoit le rattachement en paramètre d'adresse.
  const createNew = () => {
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
    if (!existing || !kind) return;
    setError(null);
    const [path, opKind, body] =
      kind === "spouse"
        ? (["/unions", "add_union", { person_a_id: person.id, person_b_id: existing, kind: unionKind, rank }] as const)
        : ([
            "/relations/parent-child",
            "add_parent_child",
            kind === "child"
              ? { parent_id: person.id, child_id: existing, kind: linkKind }
              : { parent_id: existing, child_id: person.id, kind: linkKind },
          ] as const);
    try {
      const outcome = await run(() => api(path, { method: "POST", body }), opKind, body);
      if (outcome.status === "cancelled") return;
      if (outcome.status === "done") message.success("Lien enregistré.");
      setExisting(undefined);
      onClose();
      onDone();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <Modal
      open={!!kind}
      onCancel={onClose}
      footer={null}
      title={kind ? `Ajouter ${LABEL[kind]} à ${person.first_name}` : ""}
      destroyOnHidden
    >
      <p style={{ marginTop: 0 }}>Cette personne n'est pas encore dans l'arbre ?</p>
      <Button type="primary" onClick={createNew}>
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
