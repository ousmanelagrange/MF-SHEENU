// Confirmer la réunion de sa famille à une autre, depuis le lien reçu (/reunir/:code).
// L'utilisateur choisit laquelle de ses familles (dont il est administrateur) rejoint l'autre.

import { Alert, App, Button, Popconfirm, Radio, Result, Space, Spin } from "antd";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { NtienyaBand, Wordmark } from "../../components/Ntienya";
import { api, session } from "../../lib/api";
import { useFamily } from "../../lib/family";
import { count } from "../../lib/text";
import type { MyFamily } from "../../types";

type Preview = { target_family_name: string; requested_by: string; expires_at: string; valid: boolean };
type MergeResult = { target_family_id: string; persons: number; links: number; unions: number; new_members: number; merged_accounts: number };

export function MergeJoinPage() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const { select } = useFamily();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [families, setFamilies] = useState<MyFamily[]>([]);
  const [choice, setChoice] = useState<string>();
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<MergeResult | null>(null);

  useEffect(() => {
    api<Preview>(`/family-merges/token/${token}`, { family: false })
      .then(setPreview)
      .catch(() => setError("Ce code de réunion n'existe pas. Vérifiez qu'il a été copié en entier."));
    void api<MyFamily[]>("/families", { family: false }).then((all) => {
      const admin = all.filter((f) => f.role === "admin");
      setFamilies(admin);
      if (admin.length === 1) setChoice(admin[0].id);
    });
  }, [token]);

  const accept = async () => {
    if (!choice) return;
    session.setFamily(choice); // l'API agit depuis la famille qui rejoint l'autre
    try {
      const r = await api<MergeResult>(`/family-merges/token/${token}/accept`, { method: "POST" });
      setDone(r);
      select(r.target_family_id);
    } catch (e) {
      setError((e as Error).message);
      message.error((e as Error).message);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--cotton)" }}>
      <NtienyaBand height={10} />
      <div className="page" style={{ maxWidth: 640 }}>
        <Wordmark />
        <div style={{ marginTop: 40 }}>
          {!preview && !error && <Spin />}
          {error && !preview && <Result status="warning" title="Code introuvable" subTitle={error} />}
          {done && (
            <Result
              status="success"
              title={`Votre famille a rejoint « ${preview?.target_family_name} »`}
              subTitle={`Transférés : ${count(done.persons, "personne")}, ${count(done.links, "filiation")}, ${count(done.unions, "union")}. Nouveaux membres : ${done.new_members}.`}
              extra={
                <Button type="primary" onClick={() => navigate("/arbre")}>
                  Voir l'arbre
                </Button>
              }
            />
          )}
          {preview && !done && (
            <>
              <h1 className="page__title">Rejoindre « {preview.target_family_name} »</h1>
              <p className="page__lead">
                {preview.requested_by} propose de réunir votre famille à la sienne. Toutes vos personnes, filiations, unions,
                titres et membres y seront transférés, et votre espace actuel sera fermé. Cette opération est définitive.
              </p>
              {!preview.valid && <Alert type="warning" showIcon message="Ce code a expiré ou a déjà servi." />}
              {preview.valid && families.length === 0 && (
                <Alert type="info" showIcon message="Seul l'administrateur d'une famille peut la réunir à une autre." />
              )}
              {preview.valid && families.length > 0 && (
                <>
                  <p style={{ marginTop: 24, fontWeight: 500 }}>Quelle famille rejoint « {preview.target_family_name} » ?</p>
                  <Radio.Group value={choice} onChange={(e) => setChoice(e.target.value)}>
                    <Space direction="vertical">
                      {families.map((f) => (
                        <Radio key={f.id} value={f.id}>
                          {f.name}
                        </Radio>
                      ))}
                    </Space>
                  </Radio.Group>
                  {error && <Alert type="error" showIcon message={error} style={{ marginTop: 16 }} />}
                  <div style={{ marginTop: 24 }}>
                    <Popconfirm
                      title="Réunir définitivement ?"
                      description="Votre espace actuel sera fermé après le transfert."
                      okText="Réunir"
                      cancelText="Annuler"
                      okButtonProps={{ danger: true }}
                      onConfirm={accept}
                      disabled={!choice}
                    >
                      <Button type="primary" disabled={!choice}>
                        Réunir les deux familles
                      </Button>
                    </Popconfirm>
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
