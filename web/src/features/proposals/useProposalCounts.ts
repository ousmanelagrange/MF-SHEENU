// Compteurs du menu « Propositions » : à valider (chefs de branche, bureau) et mes propositions en attente.
// Rafraîchis à chaque changement de page et toutes les minutes.

import { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { api } from "../../lib/api";
import { useFamily } from "../../lib/family";

export type ProposalCounts = { to_review: number; mine_pending: number };

export function useProposalCounts(): ProposalCounts {
  const { family } = useFamily();
  const { pathname } = useLocation();
  const [counts, setCounts] = useState<ProposalCounts>({ to_review: 0, mine_pending: 0 });

  useEffect(() => {
    if (!family) return;
    const load = () => api<ProposalCounts>("/proposals/counts").then(setCounts).catch(() => undefined);
    void load();
    const timer = window.setInterval(load, 60_000);
    return () => window.clearInterval(timer);
  }, [family, pathname]);

  return counts;
}
