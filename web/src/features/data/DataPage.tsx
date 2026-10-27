// Données de l'arbre (administrateur) : import et export GEDCOM, doublons à fusionner.

import { InboxOutlined } from "@ant-design/icons";
import { App, Button, Empty, Popconfirm, Spin, Upload } from "antd";
import { useCallback, useEffect, useState } from "react";
import { PageHead } from "../../components/AppShell";
import { PersonLine } from "../../components/Person";
import { api } from "../../lib/api";
import { useFamily } from "../../lib/family";
import type { PersonSummary } from "../../types";
import { download } from "../tree/exporter";

type Pair = { a: PersonSummary; b: PersonSummary };
type ImportResult = { persons: number; unions: number; links: number };

export function DataPage() {
  const { message } = App.useApp();
  const { family } = useFamily();
  const [pairs, setPairs] = useState<Pair[] | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  const loadDuplicates = useCallback(() => {
    setPairs(null);
    void api<Pair[]>("/duplicates").then(setPairs);
  }, []);
  useEffect(loadDuplicates, [loadDuplicates]);

  const importFile = async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    try {
      const r = await api<ImportResult>("/import/gedcom", { method: "POST", form });
      setResult(r);
      message.success("Import terminé.");
      loadDuplicates();
    } catch (e) {
      message.error((e as Error).message);
    }
    return false;
  };

  const exportFile = async () => {
    const res = await api<Response>("/export/gedcom", { raw: true });
    download(await res.blob(), `${family?.name ?? "famille"}.ged`);
  };

  const merge = async (keep: string, other: string) => {
    try {
      await api(`/persons/${keep}/merge`, { method: "POST", body: { other_id: other } });
      message.success("Fiches fusionnées.");
      loadDuplicates();
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <PageHead
        title="Données de l'arbre"
        lead="GEDCOM est le format standard de la généalogie : il permet de reprendre un arbre existant ou d'en garder une copie complète."
        actions={<Button onClick={exportFile}>Exporter en GEDCOM</Button>}
      />

      <section className="kin-group">
        <h2>Importer un fichier GEDCOM</h2>
        <Upload.Dragger accept=".ged,text/plain" showUploadList={false} beforeUpload={importFile} style={{ maxWidth: 560 }}>
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">Déposer un fichier .ged, ou cliquer pour le choisir</p>
          <p className="ant-upload-hint">Les personnes sont ajoutées à l'arbre actuel. Les doublons apparaissent ci-dessous.</p>
        </Upload.Dragger>
        {result && (
          <p style={{ marginTop: 12 }}>
            {result.persons} personnes, {result.unions} unions et {result.links} filiations importées.
          </p>
        )}
      </section>

      <section className="kin-group" style={{ marginTop: 40 }}>
        <h2>Doublons possibles</h2>
        <p style={{ color: "var(--muted)", marginTop: 0, maxWidth: "62ch" }}>
          Même prénom et même nom, années de naissance proches. Vérifiez qu'il s'agit bien de la même personne, puis
          choisissez la fiche à garder : l'autre lui transmet ses liens, ses titres et les informations manquantes.
        </p>
        {!pairs ? (
          <Spin />
        ) : pairs.length === 0 ? (
          <Empty description="Aucun doublon détecté." />
        ) : (
          <ul className="kin-list">
            {pairs.map(({ a, b }) => (
              <li key={`${a.id}-${b.id}`} className="dup-row">
                {[a, b].map((keep) => {
                  const other = keep === a ? b : a;
                  return (
                    <div key={keep.id} className="dup-cell">
                      <PersonLine person={keep} />
                      <Popconfirm
                        title="Garder cette fiche ?"
                        description={`${other.display_name} y sera fusionnée puis archivée.`}
                        okText="Fusionner"
                        cancelText="Annuler"
                        onConfirm={() => merge(keep.id, other.id)}
                      >
                        <Button size="small">Garder celle-ci</Button>
                      </Popconfirm>
                    </div>
                  );
                })}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
