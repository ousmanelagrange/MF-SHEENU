// Lien de rattachement de la famille (administrateur) : un seul lien pour toute la famille,
// à poster dans le groupe WhatsApp. Le remplacer rend l'ancien inutilisable.

import { App, Button, Popconfirm, Space } from "antd";
import { useEffect, useState } from "react";
import { ShareInviteModal } from "../../components/ShareInviteModal";
import { api } from "../../lib/api";

type LinkState = { active: boolean; created_at: string | null; link: string | null; share_text: string | null };

export function JoinLinkSection() {
  const { message } = App.useApp();
  const [state, setState] = useState<LinkState | null>(null);
  const [share, setShare] = useState<string | null>(null);

  useEffect(() => void api<LinkState>("/join-link").then(setState), []);

  const create = async () => {
    const s = await api<LinkState>("/join-link", { method: "POST" });
    setState(s);
    setShare(s.share_text);
  };
  const disable = async () => {
    await api("/join-link", { method: "DELETE" });
    setState({ active: false, created_at: state?.created_at ?? null, link: null, share_text: null });
    message.success("Lien désactivé.");
  };

  return (
    <section className="join-link">
      <div>
        <h2>Lien de rattachement</h2>
        <p>
          Un seul lien pour toute la famille, à poster dans le groupe WhatsApp. Chacun se présente ; vous placez ensuite la personne dans
          l'arbre.
          {state?.active && state.created_at && ` Lien actif depuis le ${new Date(state.created_at).toLocaleDateString("fr-FR")}.`}
        </p>
      </div>
      <Space wrap>
        {state?.active ? (
          <>
            <Popconfirm title="L'ancien lien cessera de fonctionner." okText="Remplacer" cancelText="Annuler" onConfirm={create}>
              <Button>Nouveau lien</Button>
            </Popconfirm>
            <Button type="text" onClick={disable}>
              Désactiver
            </Button>
          </>
        ) : (
          <Button type="primary" onClick={create}>
            Créer le lien
          </Button>
        )}
      </Space>
      <ShareInviteModal
        title="Lien de rattachement"
        shareText={share}
        onClose={() => setShare(null)}
        note="Gardez ce message : pour des raisons de sécurité, le lien n'est affiché qu'une fois. Vous pourrez en créer un nouveau."
      />
    </section>
  );
}
