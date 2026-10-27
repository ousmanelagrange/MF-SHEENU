// Choix de la famille (autant qu'on veut, comme des groupes WhatsApp) et création d'un espace familial.

import { useLogout } from "@refinedev/core";
import { Alert, Button, Form, Input, Modal, Select, Spin } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../../lib/api";
import { NtienyaBand, Wordmark } from "../../components/Ntienya";
import { useFamily } from "../../lib/family";
import { ROLE_LABELS, type MyFamily } from "../../types";

export function FamiliesPage() {
  const [items, setItems] = useState<MyFamily[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const { select, family } = useFamily();
  const { mutate: logout } = useLogout();
  const navigate = useNavigate();

  useEffect(() => {
    api<MyFamily[]>("/families", { family: false }).then(setItems);
  }, []);

  const open = (id: string) => {
    select(id);
    navigate("/");
  };

  const create = async (v: Record<string, string>) => {
    setSaving(true);
    setError(null);
    try {
      const fam = await api<MyFamily>("/families", { method: "POST", body: v, family: false });
      open(fam.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--cotton)" }}>
      <NtienyaBand height={10} />
      <div className="page" style={{ maxWidth: 720 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 48 }}>
          <Wordmark />
          <Button type="text" onClick={() => logout()}>
            Se déconnecter
          </Button>
        </div>
        <h1 className="page__title">Vos familles</h1>
        <p className="page__lead">
          Comme des groupes WhatsApp : votre famille paternelle, maternelle, votre foyer… Dans chacune vous avez
          votre rôle et votre fiche, et aucune ne voit les autres.
        </p>
        {!items ? (
          <Spin style={{ marginTop: 32 }} />
        ) : (
          <ul className="kin-list" style={{ marginTop: 32 }}>
            {items.map((f) => (
              <li key={f.id}>
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    open(f.id);
                  }}
                  style={{ padding: "18px 8px" }}
                >
                  <span>
                    <span className="pname" style={{ fontSize: 19 }}>
                      {f.name}
                    </span>
                    <span style={{ display: "block", color: "var(--muted)", fontSize: 14, marginTop: 2 }}>
                      {[f.community, ROLE_LABELS[f.role]].filter(Boolean).join(", ")}
                    </span>
                  </span>
                  <span className="kin-meta">{family?.id === f.id ? "Ouverte" : "Ouvrir"}</span>
                </a>
              </li>
            ))}
          </ul>
        )}
        {items && items.length === 0 && (
          <p style={{ marginTop: 24 }}>
            Vous n'appartenez encore à aucune famille. Ouvrez le lien d'invitation reçu sur WhatsApp, ou créez
            l'espace de votre famille si vous en êtes responsable.
          </p>
        )}
        {items && (
          <Button style={{ marginTop: 28 }} onClick={() => setCreating(true)}>
            Créer l'espace d'une famille
          </Button>
        )}
      </div>

      <Modal open={creating} onCancel={() => setCreating(false)} footer={null} title="Créer l'espace d'une famille" destroyOnHidden>
        <p style={{ color: "var(--muted)", marginTop: 0 }}>
          Vous en serez l'administrateur. Vous pourrez ensuite ajouter l'ancêtre racine et inviter les membres.
        </p>
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
        <Form layout="vertical" requiredMark={false} onFinish={create} initialValues={{ my_sex: "U" }}>
          <Form.Item name="name" label="Nom de la famille" rules={[{ required: true, min: 2 }]}>
            <Input placeholder="Famille Njoya" />
          </Form.Item>
          <Form.Item name="community" label="Communauté">
            <Input placeholder="Bamoun" />
          </Form.Item>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Form.Item name="my_first_name" label="Votre prénom" rules={[{ required: true }]}>
              <Input />
            </Form.Item>
            <Form.Item name="my_last_name" label="Votre nom">
              <Input />
            </Form.Item>
          </div>
          <Form.Item name="my_sex" label="Sexe">
            <Select
              options={[
                { value: "M", label: "Homme" },
                { value: "F", label: "Femme" },
                { value: "U", label: "Non précisé" },
              ]}
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={saving}>
            Créer l'espace
          </Button>
        </Form>
      </Modal>
    </div>
  );
}
