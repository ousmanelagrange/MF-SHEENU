// Mon compte : nom, mot de passe, appareils connectés. Indépendant de la famille choisie.

import { useLogout } from "@refinedev/core";
import { App, Button, Form, Input, Popconfirm, Spin } from "antd";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { NtienyaBand, Wordmark } from "../../components/Ntienya";
import { api, session } from "../../lib/api";
import { ago } from "../social/format";

type Me = { id: string; full_name: string; email: string | null; phone: string | null; is_platform_admin: boolean };
type Device = { id: string; created_at: string; last_used_at: string; ip: string | null; user_agent: string | null; current: boolean };
type Tokens = { access_token: string; refresh_token: string };

/** « Chrome sur Android », « Safari sur iPhone »… à partir de l'identifiant du navigateur. */
function deviceName(ua: string | null) {
  if (!ua) return "Appareil inconnu";
  const os = /iPhone|iPad/.test(ua) ? "iPhone" : /Android/.test(ua) ? "Android" : /Mac OS/.test(ua) ? "Mac" : /Windows/.test(ua) ? "Windows" : /Linux/.test(ua) ? "Linux" : "";
  const app = /Expo|okhttp|CFNetwork/.test(ua) ? "Application Sheenu" : /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : "Navigateur";
  return os ? `${app} sur ${os}` : app;
}

export function AccountPage() {
  const { message } = App.useApp();
  const { mutate: logout } = useLogout();
  const [me, setMe] = useState<Me | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [form] = Form.useForm();

  const load = () => {
    void api<Me>("/auth/me", { family: false }).then(setMe);
    void api<Device[]>("/auth/sessions", { family: false }).then(setDevices);
  };
  useEffect(load, []);

  const changePassword = async (v: { current_password: string; new_password: string }) => {
    try {
      const t = await api<Tokens>("/auth/password", { method: "POST", body: v, family: false });
      session.setTokens(t.access_token, t.refresh_token);
      message.success("Mot de passe changé. Vos autres appareils ont été déconnectés.");
      form.resetFields();
      load();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  if (!me) return <Spin style={{ margin: 48 }} />;
  return (
    <div style={{ minHeight: "100vh", background: "var(--cotton)" }}>
      <NtienyaBand height={10} />
      <div className="page" style={{ maxWidth: 720 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 40 }}>
          <Wordmark />
          <Link to="/familles">Vos familles</Link>
        </div>
        <h1 className="page__title">Mon compte</h1>
        <p className="page__lead">
          {me.full_name}, {me.email ?? me.phone}
        </p>
        {me.is_platform_admin && (
          <p style={{ marginTop: 8 }}>
            <Link to="/supervision">Ouvrir la supervision de la plateforme</Link>
          </p>
        )}

        <section className="kin-group" style={{ marginTop: 40 }}>
          <h2>Changer de mot de passe</h2>
          <Form form={form} layout="vertical" onFinish={changePassword} requiredMark={false} style={{ maxWidth: 420 }}>
            <Form.Item name="current_password" label="Mot de passe actuel" rules={[{ required: true }]}>
              <Input.Password autoComplete="current-password" />
            </Form.Item>
            <Form.Item
              name="new_password"
              label="Nouveau mot de passe"
              extra="Au moins 8 caractères. Une courte phrase se retient mieux et résiste mieux qu'un mot."
              rules={[{ required: true, min: 8, message: "Au moins 8 caractères." }]}
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit">
              Changer le mot de passe
            </Button>
          </Form>
        </section>

        <section className="kin-group" style={{ marginTop: 40 }}>
          <h2>Appareils connectés</h2>
          <ul className="kin-list">
            {devices.map((d) => (
              <li key={d.id}>
                <div className="kin-item">
                  <span>
                    <span className="pname">{deviceName(d.user_agent)}</span>
                    {d.current && <span className="pending-note">cet appareil</span>}
                    <span className="years" style={{ display: "block" }}>
                      Connecté {ago(d.created_at)}, dernière activité {ago(d.last_used_at)}
                      {d.ip ? `, adresse ${d.ip}` : ""}
                    </span>
                  </span>
                  {!d.current && (
                    <Button
                      size="small"
                      onClick={async () => {
                        await api(`/auth/sessions/${d.id}`, { method: "DELETE", family: false });
                        load();
                      }}
                    >
                      Déconnecter
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <Popconfirm
            title="Se déconnecter de tous les appareils ?"
            description="Il faudra se reconnecter partout, y compris ici."
            okText="Tout déconnecter"
            cancelText="Annuler"
            onConfirm={async () => {
              await api("/auth/logout-all", { method: "POST", family: false });
              logout();
            }}
          >
            <Button danger type="text" style={{ marginTop: 12, paddingLeft: 0 }}>
              Se déconnecter partout
            </Button>
          </Popconfirm>
        </section>
      </div>
    </div>
  );
}
