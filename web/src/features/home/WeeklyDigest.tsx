// Les nouvelles de la semaine, prêtes à être postées dans le groupe WhatsApp de la famille.

import { App, Button, Space } from "antd";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

type Digest = { text: string; share_link: string };

/** Rend le gras WhatsApp (*texte*) pour l'aperçu. */
function preview(text: string) {
  return text.split(/(\*[^*\n]+\*)/g).map((part, i) => (part.startsWith("*") && part.endsWith("*") ? <strong key={i}>{part.slice(1, -1)}</strong> : part));
}

export function WeeklyDigest() {
  const { message } = App.useApp();
  const [digest, setDigest] = useState<Digest | null>(null);
  useEffect(() => void api<Digest>("/digest").then(setDigest), []);
  if (!digest) return null;

  return (
    <section className="kin-group digest">
      <h2>Les nouvelles de la semaine</h2>
      <div className="digest__text">{preview(digest.text)}</div>
      <Space wrap style={{ marginTop: 12 }}>
        <Button type="primary" href={digest.share_link} target="_blank" rel="noreferrer">
          Partager sur WhatsApp
        </Button>
        <Button
          onClick={() => {
            void navigator.clipboard.writeText(digest.text);
            message.success("Résumé copié.");
          }}
        >
          Copier
        </Button>
      </Space>
    </section>
  );
}
