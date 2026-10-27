// Rejoindre une famille depuis un lien d'invitation : aperçu, création de compte ou connexion, acceptation.

import { Alert, Button, Result, Spin } from "antd";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api, session } from "../../lib/api";
import { useFamily } from "../../lib/family";
import type { MyFamily } from "../../types";
import { AuthLayout } from "./AuthPages";

type Preview = {
  family_name: string;
  community: string | null;
  invited_by: string;
  person_name: string | null;
  expires_at: string;
  valid: boolean;
};

export function JoinPage() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const { select } = useFamily();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);
  const loggedIn = !!session.access;
  const back = encodeURIComponent(`/rejoindre/${token}`);

  useEffect(() => {
    api<Preview>(`/invitations/token/${token}`, { family: false })
      .then(setPreview)
      .catch(() => setError("Ce lien d'invitation n'existe pas. Vérifiez qu'il a été copié en entier."));
  }, [token]);

  const accept = async () => {
    setJoining(true);
    setError(null);
    try {
      const fam = await api<MyFamily>(`/invitations/token/${token}/accept`, { method: "POST", family: false });
      select(fam.id);
      navigate("/");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setJoining(false);
    }
  };

  return (
    <AuthLayout>
      {!preview && !error && <Spin style={{ marginTop: 40 }} />}
      {error && !preview && <Result status="warning" title="Invitation introuvable" subTitle={error} />}
      {preview && (
        <>
          <h1>Rejoindre {preview.family_name}</h1>
          <p className="lead">
            {preview.invited_by} vous invite
            {preview.person_name ? ` en tant que ${preview.person_name}` : ""}
            {preview.community ? `, communauté ${preview.community}` : ""}.
          </p>
          {!preview.valid && (
            <Alert
              type="warning"
              showIcon
              message="Ce lien a expiré ou a déjà servi. Demandez-en un nouveau à la personne qui vous a invité."
            />
          )}
          {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
          {preview.valid &&
            (loggedIn ? (
              <Button type="primary" size="large" block loading={joining} onClick={accept}>
                Rejoindre la famille
              </Button>
            ) : (
              <>
                <Link to={`/inscription?suite=${back}`}>
                  <Button type="primary" size="large" block>
                    Créer mon compte
                  </Button>
                </Link>
                <p style={{ marginTop: 16, color: "var(--muted)" }}>
                  Déjà un compte ? <Link to={`/connexion?suite=${back}`}>Se connecter</Link>
                </p>
              </>
            ))}
        </>
      )}
    </AuthLayout>
  );
}
