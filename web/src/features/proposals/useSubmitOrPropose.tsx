// Tente une modification directe ; si elle sort du périmètre de l'utilisateur,
// propose de l'envoyer en proposition au chef de branche (RG-13, RG-14).

import { App, Input } from "antd";
import { useRef } from "react";
import { api, ApiError } from "../../lib/api";

export type ProposalKind =
  | "create_person"
  | "update_person"
  | "archive_person"
  | "add_parent_child"
  | "add_union"
  | "delete_parent_child"
  | "delete_union";

type Outcome<T> = { status: "done"; result: T } | { status: "proposed" } | { status: "cancelled" };

export function useSubmitOrPropose() {
  const { modal, message } = App.useApp();
  const note = useRef("");

  /** Envoie la proposition après confirmation ; renvoie true si elle est partie. */
  const propose = (kind: ProposalKind, payload: object) =>
    new Promise<boolean>((resolve) => {
      note.current = "";
      modal.confirm({
        title: "Envoyer une proposition ?",
        content: (
          <>
            <p style={{ marginTop: 0 }}>
              Cette modification sort de votre périmètre. Elle sera appliquée quand le chef de branche ou
              le bureau l'aura validée.
            </p>
            <Input.TextArea
              placeholder="Message pour le valideur (facultatif) : source, contexte…"
              autoSize={{ minRows: 2 }}
              onChange={(e) => (note.current = e.target.value)}
            />
          </>
        ),
        okText: "Envoyer la proposition",
        cancelText: "Annuler",
        onOk: async () => {
          await api("/proposals", { method: "POST", body: { kind, payload, message: note.current || null } });
          message.success("Proposition envoyée. Vous la suivez dans « Propositions ».");
          resolve(true);
        },
        onCancel: () => resolve(false),
      });
    });

  /** Exécute `direct` ; en cas de refus de périmètre, bascule sur une proposition. */
  async function run<T>(direct: () => Promise<T>, kind: ProposalKind, payload: object): Promise<Outcome<T>> {
    try {
      return { status: "done", result: await direct() };
    } catch (e) {
      if (e instanceof ApiError && e.code === "out_of_scope") {
        return (await propose(kind, payload)) ? { status: "proposed" } : { status: "cancelled" };
      }
      throw e;
    }
  }

  return { run, propose };
}
