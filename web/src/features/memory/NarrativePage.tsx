// Un récit : l'enregistrement, puis une édition bilingue (deux couches côte à côte, au choix),
// avec propositions de correction et relecture par les gardiens de la mémoire.

import { App, Button, Empty, Popconfirm, Select, Spin } from "antd";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { PersonLine } from "../../components/Person";
import { api } from "../../lib/api";
import type { LayerName, Narrative } from "../../types";
import { ProposeModal, ReviewDrawer } from "./components/TextVersionModals";
import { LAYERS, when } from "./format";

export function NarrativePage() {
  const { id } = useParams();
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [n, setN] = useState<Narrative | null>(null);
  const [chosen, setShown] = useState<[LayerName, LayerName] | null>(null);
  const [proposing, setProposing] = useState<LayerName | null>(null);
  const [reviewing, setReviewing] = useState<LayerName | null>(null);

  const load = useCallback(() => void api<Narrative>(`/narratives/${id}`).then(setN), [id]);
  useEffect(load, [load]);

  if (!n) return <Spin style={{ display: "block", margin: 60 }} />;

  const meta = [n.language, when(n), n.place].filter(Boolean) as string[];
  // Par défaut : la langue du récit à gauche, sa traduction à droite (l'anglais si le récit est en français)
  const shown = chosen ?? (["original", /^fran/i.test(n.language ?? "") ? "en" : "fr"] as [LayerName, LayerName]);

  return (
    <div className="page narrative">
      <p className="crumb">
        <Link to="/memoire">Récits</Link>
      </p>
      <header className="narrative__head">
        <h1 className="page__title">{n.title}</h1>
        {n.teller && (
          <p className="narrative__teller">
            Raconté par <PersonLine person={n.teller} size={24} />
          </p>
        )}
        {meta.length > 0 && (
          <p className="narrative__meta">
            {meta.map((m) => (
              <span key={m}>{m}</span>
            ))}
          </p>
        )}
      </header>

      {n.media_url &&
        (n.media_kind === "video" ? (
          <video className="narrative__media" src={n.media_url} controls preload="metadata" />
        ) : (
          <audio className="narrative__media" src={n.media_url} controls preload="metadata" />
        ))}

      <div className="edition">
        {shown.map((layer, i) => {
          const state = n.texts[layer];
          const current = state.validated;
          return (
            <section key={i} className="edition__col">
              <div className="edition__bar">
                <Select
                  size="small"
                  variant="borderless"
                  value={layer}
                  onChange={(v) => setShown(i === 0 ? [v, shown[1]] : [shown[0], v])}
                  options={LAYERS.map((l) => ({ value: l.key, label: l.label }))}
                  popupMatchSelectWidth={false}
                />
                {n.can_review && state.pending > 0 && (
                  <Button size="small" type="text" className="pending-note" onClick={() => setReviewing(layer)}>
                    {state.pending} à relire
                  </Button>
                )}
              </div>
              {current ? (
                <>
                  <div className="reading">{current.text}</div>
                  <p className="edition__credit">
                    Texte de {current.author.name}
                    {!n.can_review && state.pending > 0 && `, ${state.pending} proposition${state.pending > 1 ? "s" : ""} en relecture`}
                  </p>
                </>
              ) : (
                <p className="edition__empty">
                  {layer === "original" ? "Pas encore de transcription." : "Pas encore de traduction."}
                  {state.pending > 0 && ` ${state.pending} proposition${state.pending > 1 ? "s" : ""} en relecture.`}
                </p>
              )}
              <Button size="small" onClick={() => setProposing(layer)}>
                {current ? "Proposer une correction" : layer === "original" ? "Transcrire" : "Traduire"}
              </Button>
            </section>
          );
        })}
      </div>

      {n.persons.length > 0 && (
        <section className="kin-group">
          <h2>Personnes dont parle le récit</h2>
          <div className="person-chips">
            {n.persons.map((p) => (
              <PersonLine key={p.id} person={p} size={28} />
            ))}
          </div>
        </section>
      )}

      <footer className="narrative__foot">
        <span className="years">Enregistré par {n.recorded_by.name}</span>
        {n.can_edit && (
          <Popconfirm
            title="Supprimer ce récit et toutes ses versions ?"
            okText="Supprimer"
            cancelText="Annuler"
            onConfirm={async () => {
              await api(`/narratives/${n.id}`, { method: "DELETE" });
              message.success("Récit supprimé.");
              navigate("/memoire");
            }}
          >
            <Button type="text" danger>
              Supprimer le récit
            </Button>
          </Popconfirm>
        )}
      </footer>

      {!n.media_url && Object.values(n.texts).every((t) => !t.validated && !t.pending) && (
        <Empty description="Ce récit n'a encore ni enregistrement ni texte." />
      )}

      <ProposeModal
        narrativeId={n.id}
        layer={proposing}
        initial={proposing ? (n.texts[proposing].validated?.text ?? "") : ""}
        curator={n.can_review}
        onClose={() => setProposing(null)}
        onSaved={load}
      />
      <ReviewDrawer
        narrativeId={n.id}
        layer={reviewing}
        current={reviewing ? (n.texts[reviewing].validated?.text ?? null) : null}
        onClose={() => setReviewing(null)} onDone={load} />
    </div>
  );
}
