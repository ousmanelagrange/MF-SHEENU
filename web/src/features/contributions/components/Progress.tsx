// Barre d'avancement d'une collecte : collecté sur objectif, et nombre de personnes à jour.

import type { ContributionEvent } from "../../../types";
import { money, progress } from "../format";

export function Progress({ event, compact = false }: { event: ContributionEvent; compact?: boolean }) {
  const { target, ratio } = progress(event);
  const t = event.totals;
  return (
    <div className="collect">
      <div className="collect__figures">
        <span className="collect__amount">{money(t.collected, event.currency)}</span>
        {target > 0 && (
          <span className="collect__target">
            sur {money(target, event.currency)}, {Math.round(ratio * 100)} %
          </span>
        )}
      </div>
      <div className="collect__bar" role="progressbar" aria-valuenow={Math.round(ratio * 100)} aria-valuemin={0} aria-valuemax={100}>
        <div style={{ width: `${ratio * 100}%` }} />
      </div>
      {!compact && t.persons_due > 0 && (
        <p className="collect__counts">
          {t.paid} à jour, {t.partial} partiels, {t.unpaid} non payés
          {t.pending > 0 ? `, ${money(t.pending, event.currency)} en attente de validation` : ""}
        </p>
      )}
    </div>
  );
}
