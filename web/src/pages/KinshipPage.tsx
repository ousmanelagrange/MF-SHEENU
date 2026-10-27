import { Button, Spin } from "antd";
import { Fragment, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../api";
import { PageHead } from "../components/AppShell";
import { Avatar, PersonPicker } from "../components/Person";
import { useFamily } from "../family";
import type { Kinship } from "../types";

export function KinshipPage() {
  const { family } = useFamily();
  const [params, setParams] = useSearchParams();
  const from = params.get("de") ?? family?.person_id ?? undefined;
  const to = params.get("a") ?? undefined;
  const [result, setResult] = useState<Kinship | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setResult(null);
    if (!from || !to) return;
    setLoading(true);
    api<Kinship>("/kinship", { query: { from, to } })
      .then(setResult)
      .finally(() => setLoading(false));
  }, [from, to]);

  const set = (key: "de" | "a", value?: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };

  const fromName = result?.path[0]?.first_name;
  const toName = result?.path[result.path.length - 1]?.first_name;

  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <PageHead
        title="Lien de parenté"
        lead="Choisissez deux personnes : Sheenu trouve leur ancêtre commun le plus proche et nomme le lien."
      />
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 12, alignItems: "center" }}>
        <PersonPicker value={from} onChange={(v) => set("de", v)} placeholder="Première personne" />
        <Button
          type="text"
          aria-label="Inverser"
          onClick={() => {
            const next = new URLSearchParams(params);
            if (to) next.set("de", to);
            if (from) next.set("a", from);
            setParams(next);
          }}
        >
          ⇄
        </Button>
        <PersonPicker value={to} onChange={(v) => set("a", v)} placeholder="Seconde personne" />
      </div>

      {loading && <Spin style={{ marginTop: 32 }} />}
      {result && (
        <div className="kin-result">
          {result.related ? (
            <>
              <p className="kin-result__label">
                {result.relation_type === "self"
                  ? "C'est la même personne."
                  : result.label && result.label.charAt(0).toUpperCase() + result.label.slice(1)}
              </p>
              {result.relation_type !== "self" && (
                <p style={{ color: "var(--muted)", margin: 0 }}>
                  C'est ce que {toName} est pour {fromName}
                  {result.distance_from != null && result.distance_to != null
                    ? `, à ${result.distance_from + result.distance_to} degrés par l'ancêtre commun.`
                    : "."}
                </p>
              )}
              <div className="kin-path">
                {result.path.map((p, i) => (
                  <Fragment key={p.id}>
                    {i > 0 && <span className="kin-path__sep">›</span>}
                    <Link
                      to={`/personnes/${p.id}`}
                      className={`kin-path__step${p.id === result.common_ancestor_id ? " kin-path__step--common" : ""}`}
                    >
                      <Avatar person={p} size={26} />
                      <span>{p.display_name}</span>
                    </Link>
                  </Fragment>
                ))}
              </div>
              {result.common_ancestor_id && (
                <p style={{ color: "var(--muted)", fontSize: 13.5, marginTop: 14, marginBottom: 0 }}>
                  En doré : l'ancêtre commun.
                </p>
              )}
            </>
          ) : (
            <p style={{ margin: 0 }}>
              Aucun lien trouvé dans l'arbre entre ces deux personnes. Il manque peut-être un parent ou une union.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
