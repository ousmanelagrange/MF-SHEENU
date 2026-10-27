// « Réunir deux familles » (administrateur) : générer un code pour accueillir une autre
// famille, à envoyer à son administrateur. La confirmation se fait sur /reunir/:code.

import { App, Button } from "antd";
import { useState } from "react";
import { ShareInviteModal } from "../../components/ShareInviteModal";
import { api } from "../../lib/api";

export function MergeSection() {
  const { message } = App.useApp();
  const [shareText, setShareText] = useState<string | null>(null);

  const create = async () => {
    try {
      const r = await api<{ share_text: string }>("/family-merges", { method: "POST", body: {} });
      setShareText(r.share_text);
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  return (
    <section className="kin-group" style={{ marginTop: 40 }}>
      <h2>Réunir deux familles</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, maxWidth: "62ch" }}>
        Un foyer ou une branche a créé son propre espace et veut rejoindre cette famille ? Envoyez ce code à son
        administrateur. Quand il confirme, ses personnes, liens, titres et membres arrivent ici ; vous rattachez ensuite
        le foyer au bon endroit de l'arbre.
      </p>
      <Button onClick={create}>Générer un code de réunion</Button>
      <ShareInviteModal title="Code de réunion" shareText={shareText} onClose={() => setShareText(null)} />
    </section>
  );
}
