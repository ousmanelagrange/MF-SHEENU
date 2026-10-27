// Page du lien de rattachement (/rattachement/:token) : le visiteur voit seulement le nom de
// la famille, crée son compte ou se connecte, puis explique comment il s'y rattache.

import { Alert, Button, Form, Input, InputNumber, Result, Select, Spin } from "antd";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api, session } from "../../lib/api";
import { NtienyaMark } from "../../components/Ntienya";
import { AuthLayout } from "../auth/AuthPages";

type Preview = { family_name: string; community: string | null; already_member: boolean; request_status: string | null };

export function JoinRequestPage() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const loggedIn = !!session.access;
  const back = encodeURIComponent(`/rattachement/${token}`);

  useEffect(() => {
    if (!loggedIn) return;
    api<Preview>(`/join/${token}`, { family: false })
      .then(setPreview)
      .catch(() => setError("Ce lien n'existe pas ou a été remplacé. Demandez le nouveau lien dans le groupe de la famille."));
  }, [token, loggedIn]);

  const send = async (v: Record<string, unknown>) => {
    setSending(true);
    setError(null);
    try {
      setPreview(await api<Preview>(`/join/${token}`, { method: "POST", body: v, family: false }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  };

  if (!loggedIn) {
    return (
      <AuthLayout>
        <h1>Rejoindre votre famille sur Sheenu</h1>
        <p className="lead">Créez votre compte ou connectez-vous : vous pourrez ensuite vous présenter à la famille.</p>
        <Link to={`/inscription?suite=${back}`}>
          <Button type="primary" size="large" block>
            Créer mon compte
          </Button>
        </Link>
        <p style={{ marginTop: 16, color: "var(--muted)" }}>
          Déjà un compte ? <Link to={`/connexion?suite=${back}`}>Se connecter</Link>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      {!preview && !error && <Spin style={{ marginTop: 40 }} />}
      {error && !preview && <Result status="warning" title="Lien introuvable" subTitle={error} />}
      {preview?.already_member && (
        <Result
          icon={<NtienyaMark size={56} />}
          title={`Vous faites partie de ${preview.family_name}`}
          extra={
            <Button type="primary" onClick={() => navigate("/familles")}>
              Ouvrir la famille
            </Button>
          }
        />
      )}
      {preview && !preview.already_member && preview.request_status === "pending" && (
        <Result
          icon={<NtienyaMark size={56} />}
          title="Demande envoyée"
          subTitle={`Le bureau de ${preview.family_name} va relire votre demande et vous placer dans l'arbre. Vous serez prévenu(e) dès que c'est fait.`}
        />
      )}
      {preview && !preview.already_member && preview.request_status !== "pending" && (
        <>
          <h1>Se rattacher à {preview.family_name}</h1>
          <p className="lead">
            Dites qui vous êtes et comment vous vous rattachez à la famille. Le bureau ou un chef de branche vous placera dans l'arbre.
          </p>
          {preview.request_status === "rejected" && (
            <Alert type="warning" showIcon style={{ marginBottom: 16 }} message="Votre première demande n'a pas abouti. Complétez-la et renvoyez-la." />
          )}
          {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
          <Form layout="vertical" requiredMark={false} onFinish={send}>
            <div className="form-row">
              <Form.Item name="first_name" label="Prénom" rules={[{ required: true }]} style={{ flex: 1 }}>
                <Input />
              </Form.Item>
              <Form.Item name="last_name" label="Nom" style={{ flex: 1 }}>
                <Input />
              </Form.Item>
            </div>
            <div className="form-row">
              <Form.Item name="sex" label="Sexe" initialValue="U" style={{ flex: 1 }}>
                <Select
                  options={[
                    { value: "F", label: "Femme" },
                    { value: "M", label: "Homme" },
                    { value: "U", label: "Ne pas préciser" },
                  ]}
                />
              </Form.Item>
              <Form.Item name="birth_year" label="Année de naissance" style={{ flex: 1 }}>
                <InputNumber min={1900} max={2100} style={{ width: "100%" }} />
              </Form.Item>
            </div>
            <Form.Item
              name="lineage"
              label="Comment vous rattachez-vous à la famille ?"
              rules={[{ required: true, min: 3, message: "Expliquez votre lien en quelques mots." }]}
              extra="Vos parents et grands-parents, la branche, le village."
            >
              <Input.TextArea autoSize={{ minRows: 3 }} placeholder="Fille d'Issa Nchare, petite-fille de Mfon Adamou, branche de Foumbot" />
            </Form.Item>
            <div className="form-row">
              <Form.Item name="village" label="Village d'origine" style={{ flex: 1 }}>
                <Input />
              </Form.Item>
              <Form.Item name="country" label="Pays où vous vivez" style={{ flex: 1 }}>
                <Input />
              </Form.Item>
            </div>
            <Form.Item name="phone" label="Téléphone (WhatsApp)">
              <Input />
            </Form.Item>
            <Button type="primary" htmlType="submit" size="large" block loading={sending}>
              Envoyer ma demande
            </Button>
          </Form>
        </>
      )}
    </AuthLayout>
  );
}
