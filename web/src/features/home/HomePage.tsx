// Accueil de la famille : chiffres clés, ma place dans la famille, répartition par génération et par pays.

import { Button, Spin } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../../lib/api";
import { PageHead } from "../../components/AppShell";
import { PersonLine } from "../../components/Person";
import { useFamily } from "../../lib/family";
import type { PersonDetail, Stats } from "../../types";

export function HomePage() {
  const { family } = useFamily();
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats | null>(null);
  const [me, setMe] = useState<PersonDetail | null>(null);

  useEffect(() => {
    api<Stats>("/stats").then(setStats);
    if (family?.person_id) api<PersonDetail>(`/persons/${family.person_id}`).then(setMe);
  }, [family?.person_id]);

  if (!stats || !family) return <Spin style={{ margin: 48 }} />;
  const gens = Object.entries(stats.by_generation).sort((a, b) => Number(a[0]) - Number(b[0]));
  const maxGen = Math.max(1, ...gens.map(([, n]) => n));
  const countries = Object.entries(stats.by_country).slice(0, 6);

  return (
    <div className="page">
      <PageHead
        title={family.name}
        lead={family.description ?? (family.community ? `Communauté ${family.community}` : undefined)}
        actions={
          <>
            <Button type="primary" onClick={() => navigate("/arbre")}>
              Voir l'arbre
            </Button>
            <Button onClick={() => navigate("/personnes/nouvelle")}>Ajouter une personne</Button>
          </>
        }
      />

      <div className="stat-strip">
        <div>
          <b>{stats.persons}</b>
          <span>personnes dans l'arbre</span>
        </div>
        <div>
          <b>{stats.generations}</b>
          <span>générations</span>
        </div>
        <div>
          <b>{stats.living}</b>
          <span>vivants</span>
        </div>
        <div>
          <b>{stats.members}</b>
          <span>membres inscrits</span>
        </div>
      </div>

      {!family.root_person_id && family.role === "admin" && (
        <p style={{ background: "var(--brass-soft)", padding: "14px 18px", borderRadius: 8, marginBottom: 32 }}>
          L'ancêtre racine n'est pas encore défini. Ajoutez la personne la plus ancienne connue, puis
          ouvrez sa fiche et choisissez « Définir comme racine ».
        </p>
      )}

      <div className="home-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 48 }}>
        <section className="kin-group">
          <h2>Ma place dans la famille</h2>
          {me ? (
            <ul className="kin-list">
              <li>
                <div className="kin-item">
                  <PersonLine person={me} />
                </div>
              </li>
              {me.parents.map((p) => (
                <li key={p.relation_id}>
                  <div className="kin-item">
                    <PersonLine person={p.person} />
                    <span className="kin-meta">{p.person.sex === "F" ? "mère" : "père"}</span>
                  </div>
                </li>
              ))}
              {me.parents.length === 0 && (
                <li>
                  <div className="kin-item" style={{ color: "var(--muted)" }}>
                    Vos parents ne sont pas encore rattachés.
                  </div>
                </li>
              )}
            </ul>
          ) : (
            <p className="empty-note">Votre compte n'est pas relié à une fiche.</p>
          )}
        </section>

        <section className="kin-group">
          <h2>Personnes par génération</h2>
          <div className="gen-bars">
            {gens.map(([g, n]) => (
              <div key={g} className="gen-bars__row">
                <span>Génération {g}</span>
                <div className="gen-bars__bar" style={{ width: `${(n / maxGen) * 100}%` }} />
                <span>{n}</span>
              </div>
            ))}
          </div>
          <h2 style={{ marginTop: 32 }}>Où vit la famille</h2>
          <div className="gen-bars">
            {countries.map(([c, n]) => (
              <div key={c} className="gen-bars__row">
                <span>{c}</span>
                <div className="gen-bars__bar" style={{ width: `${(n / stats.persons) * 100}%`, background: "var(--brass)" }} />
                <span>{n}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
