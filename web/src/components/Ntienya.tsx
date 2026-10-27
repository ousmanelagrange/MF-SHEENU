// Motifs inspirés du ntienya (ndop) : losanges en réserve blanche sur fond indigo.
// La marque superpose quatre losanges en treillis, lecture double : le tissu et l'arbre
// (un ancêtre, deux enfants, une descendance).

import { palette } from "../theme";

export function NtienyaMark({ size = 32, inverted = false }: { size?: number; inverted?: boolean }) {
  const ground = inverted ? "#F4F5F8" : palette.indigo700;
  const ink = inverted ? palette.indigo700 : "#F4F5F8";
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role="img" aria-label="Sheenu">
      <rect width="48" height="48" rx="9" fill={ground} />
      <g fill="none" stroke={ink} strokeWidth="2" strokeLinejoin="round">
        <path d="M24 7l7 7-7 7-7-7z" />
        <path d="M15 18l7 7-7 7-7-7z" />
        <path d="M33 18l7 7-7 7-7-7z" />
        <path d="M24 27l7 7-7 7-7-7z" />
      </g>
      <g fill={ink}>
        <path d="M24 12l2 2-2 2-2-2z" />
        <path d="M15 23l2 2-2 2-2-2z" />
        <path d="M33 23l2 2-2 2-2-2z" />
        <path d="M24 32l2 2-2 2-2-2z" />
      </g>
    </svg>
  );
}

export function Wordmark({ inverted = false }: { inverted?: boolean }) {
  return (
    <span className={`wordmark${inverted ? " wordmark--inv" : ""}`}>
      <NtienyaMark size={30} inverted={inverted} />
      <span className="wordmark__text">Sheenu</span>
    </span>
  );
}

/** Bande de tissu répétée : rangée de losanges réservés, points de couture, zigzag. */
export function NtienyaBand({ height = 44, opacity = 1 }: { height?: number; opacity?: number }) {
  const id = "ntienya-band";
  return (
    <svg width="100%" height={height} aria-hidden="true" style={{ display: "block", opacity }}>
      <defs>
        <pattern id={id} width="28" height="44" patternUnits="userSpaceOnUse">
          <rect width="28" height="44" fill={palette.indigo700} />
          <path d="M14 8l8 8-8 8-8-8z" fill="none" stroke="#E9ECF4" strokeWidth="1.6" />
          <path d="M14 13.5l2.5 2.5-2.5 2.5-2.5-2.5z" fill="#E9ECF4" />
          <path d="M0 34l7-5 7 5 7-5 7 5" fill="none" stroke="#E9ECF4" strokeWidth="1.3" />
          <circle cx="0" cy="4" r="0.9" fill="#E9ECF4" />
          <circle cx="7" cy="4" r="0.9" fill="#E9ECF4" />
          <circle cx="14" cy="4" r="0.9" fill="#E9ECF4" />
          <circle cx="21" cy="4" r="0.9" fill="#E9ECF4" />
          <circle cx="28" cy="4" r="0.9" fill="#E9ECF4" />
          <circle cx="3.5" cy="40" r="0.9" fill="#E9ECF4" />
          <circle cx="10.5" cy="40" r="0.9" fill="#E9ECF4" />
          <circle cx="17.5" cy="40" r="0.9" fill="#E9ECF4" />
          <circle cx="24.5" cy="40" r="0.9" fill="#E9ECF4" />
        </pattern>
      </defs>
      <rect width="100%" height={height} fill={`url(#${id})`} />
    </svg>
  );
}

/** Grand panneau de tissu pour les écrans d'accueil. */
export function NtienyaCloth() {
  const id = "ntienya-cloth";
  return (
    <svg width="100%" height="100%" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
      <defs>
        <pattern id={id} width="96" height="96" patternUnits="userSpaceOnUse">
          <rect width="96" height="96" fill={palette.indigo700} />
          <g fill="none" stroke="#DCE1EE" strokeWidth="1.6" opacity="0.9">
            <path d="M48 6l18 18-18 18-18-18z" />
            <path d="M48 14l10 10-10 10-10-10z" />
            <path d="M0 54l18 18L0 90M96 54L78 72l18 18" />
            <path d="M30 72l18-18 18 18-18 18z" />
          </g>
          <g fill="#DCE1EE" opacity="0.9">
            <path d="M48 20l4 4-4 4-4-4z" />
            <path d="M48 68l4 4-4 4-4-4z" />
            <circle cx="12" cy="12" r="1.3" />
            <circle cx="84" cy="12" r="1.3" />
            <circle cx="12" cy="36" r="1.3" />
            <circle cx="84" cy="36" r="1.3" />
            <circle cx="24" cy="24" r="1.3" />
            <circle cx="72" cy="24" r="1.3" />
          </g>
          <path d="M0 47h96" stroke="#DCE1EE" strokeWidth="1" strokeDasharray="2 4" opacity="0.7" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id})`} />
    </svg>
  );
}
