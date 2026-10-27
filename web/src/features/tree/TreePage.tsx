// Page de l'arbre : choix de la vue, profondeur, recentrage, export, panneau de la personne sélectionnée.

import { DownloadOutlined, MinusOutlined, PlusOutlined, ExpandOutlined } from "@ant-design/icons";
import { Button, Drawer, Dropdown, Segmented, Select, Space, Spin, message } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { api } from "../../lib/api";
import { Avatar, PersonPicker, TitleBadges, lifeSpan } from "../../components/Person";
import { useFamily } from "../../lib/family";
import { download, exportTree } from "./exporter";
import { buildIndex, buildTree, type Mode } from "./layout";
import { TreeCanvas, type TreeCanvasHandle } from "./TreeCanvas";
import type { Kinship, Tree } from "../../types";

export function TreePage() {
  const { family } = useFamily();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [data, setData] = useState<Tree | null>(null);
  const [mode, setMode] = useState<Mode>((params.get("vue") as Mode) || "descendants");
  const [depth, setDepth] = useState(2);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<string | null>(null);
  const [kin, setKin] = useState<Kinship | null>(null);
  const [busy, setBusy] = useState(false);
  const canvas = useRef<TreeCanvasHandle>(null);

  useEffect(() => {
    api<Tree>("/tree").then(setData);
  }, []);

  const idx = useMemo(() => (data ? buildIndex(data) : null), [data]);
  const spouseRanks = useMemo(() => {
    const m = new Map<string, number | null>();
    for (const u of data?.unions ?? []) {
      m.set(`${u.person_a_id}:${u.person_b_id}`, u.rank);
      m.set(`${u.person_b_id}:${u.person_a_id}`, u.rank);
    }
    return m;
  }, [data]);

  const defaultFocus = data
    ? mode === "descendants"
      ? (data.root_person_id ?? data.me_person_id ?? data.persons[0]?.id)
      : (data.me_person_id ?? data.persons[0]?.id)
    : undefined;
  const focusId = params.get("centre") ?? defaultFocus ?? null;

  const root = useMemo(
    () => (idx && focusId ? buildTree(idx, focusId, mode, depth, expanded) : null),
    [idx, focusId, mode, depth, expanded],
  );

  useEffect(() => {
    setKin(null);
    if (selected && data?.me_person_id && selected !== data.me_person_id) {
      api<Kinship>("/kinship", { query: { to: selected } }).then(setKin).catch(() => setKin(null));
    }
  }, [selected, data?.me_person_id]);

  const center = (id: string) => {
    const next = new URLSearchParams(params);
    next.set("centre", id);
    next.set("vue", mode);
    setParams(next);
    setExpanded(new Set());
  };

  const doExport = async (format: "svg" | "png" | "pdf" | "ged") => {
    if (!family) return;
    const base = `${family.name} - arbre`.replace(/[^\p{L}\p{N} _-]/gu, "");
    setBusy(true);
    try {
      if (format === "ged") {
        const res = await api<Response>("/export/gedcom", { raw: true });
        download(await res.blob(), `${family.name}.ged`);
      } else {
        const content = canvas.current?.getContent();
        if (!content) return;
        const focus = idx?.persons.get(focusId ?? "");
        const heading =
          mode === "descendants"
            ? `Descendance de ${focus?.display_name ?? ""}`
            : `Ascendance de ${focus?.display_name ?? ""}`;
        await exportTree(content, format, `${family.name} — ${heading}`, base);
      }
      message.success("Téléchargement prêt.");
    } catch (e) {
      message.error(`Export impossible : ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  if (!data || !idx) {
    return (
      <div className="tree-stage" style={{ display: "grid", placeItems: "center" }}>
        <Spin />
      </div>
    );
  }

  const sel = selected ? idx.persons.get(selected) : null;
  const focus = focusId ? idx.persons.get(focusId) : null;

  return (
    <div className="tree-stage">
      {root ? (
        <TreeCanvas
          ref={canvas}
          root={root}
          mode={mode}
          focusId={focusId!}
          meId={data.me_person_id}
          spouseRanks={spouseRanks}
          onSelect={setSelected}
          onExpand={(id) => setExpanded((s) => new Set(s).add(id))}
        />
      ) : (
        <p className="empty-note">L'arbre est vide. Ajoutez une première personne.</p>
      )}

      <div className="tree-toolbar">
        {focus && <span className="tree-toolbar__title">{focus.display_name}</span>}
        <Segmented<Mode>
          value={mode}
          onChange={(m) => {
            setMode(m);
            const next = new URLSearchParams(params);
            next.delete("centre");
            next.set("vue", m);
            setParams(next);
            setExpanded(new Set());
          }}
          options={[
            { label: "Descendance", value: "descendants" },
            { label: "Ascendance", value: "ancestors" },
          ]}
        />
        <Select
          value={depth}
          onChange={(d) => {
            setDepth(d);
            setExpanded(new Set());
          }}
          style={{ width: 160 }}
          options={[1, 2, 3, 4, 5, 6, 8, 12].map((d) => ({ value: d, label: d === 1 ? "1 génération" : `${d} générations` }))}
        />
        <PersonPicker
          placeholder="Centrer sur…"
          style={{ width: 240 }}
          onChange={(id) => id && center(id)}
        />
        <div style={{ flex: 1 }} />
        <Dropdown
          menu={{
            items: [
              { key: "pdf", label: "PDF, pour imprimer" },
              { key: "png", label: "Image PNG" },
              { key: "svg", label: "SVG vectoriel, grand format" },
              { type: "divider" },
              { key: "ged", label: "GEDCOM, toute la famille" },
            ],
            onClick: ({ key }) => void doExport(key as "svg" | "png" | "pdf" | "ged"),
          }}
        >
          <Button icon={<DownloadOutlined />} loading={busy}>
            Télécharger
          </Button>
        </Dropdown>
      </div>

      <div className="tree-legend">
        <span>
          <i style={{ borderTop: "1.5px solid #A9B1CB" }} />
          filiation
        </span>
        <span style={{ color: "#9C7428" }}>∞ union</span>
        <span>Cliquez sur une personne pour l'ouvrir</span>
      </div>
      <div className="tree-zoom">
        <Button icon={<PlusOutlined />} aria-label="Zoomer" onClick={() => canvas.current?.zoomBy(1.25)} />
        <Button icon={<MinusOutlined />} aria-label="Dézoomer" onClick={() => canvas.current?.zoomBy(0.8)} />
        <Button icon={<ExpandOutlined />} aria-label="Tout afficher" onClick={() => canvas.current?.fit()} />
      </div>

      <Drawer
        open={!!sel}
        onClose={() => setSelected(null)}
        width={380}
        title={null}
        styles={{ body: { padding: 24 } }}
      >
        {sel && (
          <div>
            <Avatar person={sel} size={88} />
            <h2 className="profile__name" style={{ fontSize: 24 }}>
              {sel.display_name}
            </h2>
            <p className="profile__alt">
              {[sel.traditional_name, lifeSpan(sel), sel.generation ? `génération ${sel.generation}` : null]
                .filter(Boolean)
                .join(", ")}
            </p>
            <Space wrap>
              <TitleBadges titles={sel.titles} max={4} />
            </Space>
            {kin?.label && (
              <p style={{ marginTop: 18, fontSize: 15 }}>
                Pour vous : <span className="pname">{kin.label}</span>
              </p>
            )}
            <Space direction="vertical" style={{ width: "100%", marginTop: 24 }}>
              <Button type="primary" block onClick={() => navigate(`/personnes/${sel.id}`)}>
                Ouvrir la fiche
              </Button>
              <Button block onClick={() => (center(sel.id), setSelected(null))}>
                Centrer l'arbre ici
              </Button>
              {data.me_person_id && sel.id !== data.me_person_id && (
                <Link to={`/parente?de=${data.me_person_id}&a=${sel.id}`}>
                  <Button block type="text">
                    Voir le chemin de parenté
                  </Button>
                </Link>
              )}
            </Space>
          </div>
        )}
      </Drawer>
    </div>
  );
}
