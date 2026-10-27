// Libellés et mise en forme des cotisations, partagés par toutes les pages du module.

import type { ContributionEvent, DueStatus, Payment } from "../../types";

const CURRENCY: Record<string, string> = { XAF: "FCFA", XOF: "FCFA", EUR: "€", USD: "$", GBP: "£", CAD: "$ CA" };

/** 25000, "XAF" → « 25 000 FCFA ». */
export function money(amount: number, currency = "XAF") {
  // Espace insécable classique : l'espace fine du format français manque dans certaines polices.
  return `${amount.toLocaleString("fr-FR").replace(/\u202f/g, "\u00a0")} ${CURRENCY[currency] ?? currency}`;
}

export const KIND_LABELS: Record<ContributionEvent["kind"], string> = {
  mourning: "Deuil",
  wedding: "Mariage",
  birth: "Naissance",
  project: "Projet",
  annual: "Cotisation annuelle",
  other: "Autre",
};

export const STATUS_LABELS: Record<DueStatus, string> = {
  paid: "À jour",
  partial: "Partiel",
  unpaid: "Non payé",
  exempt: "Exempté",
};

export const STATUS_COLORS: Record<DueStatus, string> = {
  paid: "green",
  partial: "gold",
  unpaid: "red",
  exempt: "default",
};

export const METHOD_LABELS: Record<Payment["method"], string> = {
  mobile_money: "Mobile Money",
  cash: "Espèces",
  bank: "Virement",
  other: "Autre",
};

export const PAYMENT_STATUS: Record<Payment["status"], { label: string; color: string }> = {
  declared: { label: "À valider", color: "gold" },
  validated: { label: "Validé", color: "green" },
  rejected: { label: "Refusé", color: "red" },
};

/** Part collectée, par rapport à l'objectif s'il existe, sinon au total attendu. */
export function progress(event: ContributionEvent) {
  const target = event.target_amount || event.totals.due;
  return { target, ratio: target ? Math.min(1, event.totals.collected / target) : 0 };
}
