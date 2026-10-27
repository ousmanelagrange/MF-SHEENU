// Libellés de la supervision.

export const EVENT_LABELS: Record<string, string> = {
  login: "Connexion",
  login_failed: "Connexion refusée",
  login_locked: "Compte verrouillé",
  rate_limited: "Débit dépassé",
  foreign_family: "Accès à une famille étrangère",
  refresh_reuse: "Jeton réutilisé (vol probable)",
  bad_signature: "Webhook falsifié",
  media_bad_signature: "Lien de média invalide",
  upload_rejected: "Fichier refusé",
  server_error: "Erreur serveur",
  account_disabled: "Compte suspendu",
  password_changed: "Mot de passe changé",
};

export const ACTION_LABELS: Record<string, string> = {
  view_users: "Consultation des comptes",
  view_families: "Consultation des familles",
  disable_user: "Suspension d'un compte",
  enable_user: "Réactivation d'un compte",
  unlock_user: "Déverrouillage d'un compte",
  revoke_sessions: "Déconnexion de tous les appareils",
  purge: "Purge de maintenance",
  operator_add: "Nomination d'un opérateur",
  operator_remove: "Retrait d'un opérateur",
};

export const SEVERITY: Record<string, { label: string; color: string }> = {
  critical: { label: "Critique", color: "red" },
  warning: { label: "Alerte", color: "gold" },
  info: { label: "Info", color: "default" },
};

export function bytes(n: number | null) {
  if (n === null) return "—";
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} Ko`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} Mo`;
  return `${(n / 1024 ** 3).toFixed(2)} Go`;
}

export function duration(s: number) {
  if (s < 3600) return `${Math.round(s / 60)} min`;
  if (s < 86400) return `${Math.round(s / 3600)} h`;
  return `${Math.round(s / 86400)} j`;
}

export const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
