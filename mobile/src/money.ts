// Mise en forme des montants et libellés des cotisations (mêmes règles que le web).

import type { DueStatus } from "./types";

const CURRENCY: Record<string, string> = { XAF: "FCFA", XOF: "FCFA", EUR: "€", USD: "$", GBP: "£", CAD: "$ CA" };

/** 25000, "XAF" → « 25 000 FCFA » (formatage manuel : Intl n'est pas complet sur tous les téléphones). */
export function money(amount: number, currency = "XAF") {
  const digits = Math.round(amount).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return `${digits} ${CURRENCY[currency] ?? currency}`;
}

export const STATUS_LABELS: Record<DueStatus, string> = {
  paid: "À jour",
  partial: "Partiel",
  unpaid: "Non payé",
  exempt: "Exempté",
};

export const STATUS_COLORS: Record<DueStatus, string> = {
  paid: "#2F6B4F",
  partial: "#9C7428",
  unpaid: "#8C3A2B",
  exempt: "#5D6379",
};
