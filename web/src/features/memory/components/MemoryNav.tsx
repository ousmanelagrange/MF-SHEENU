// Onglets de la mémoire familiale : récits, albums, frise.

import { NavLink } from "react-router";

const TABS = [
  { to: "/memoire", label: "Récits", end: true },
  { to: "/memoire/albums", label: "Albums", end: false },
  { to: "/memoire/frise", label: "Frise", end: false },
];

export function MemoryNav() {
  return (
    <nav className="tabs-nav" aria-label="Mémoire">
      {TABS.map((t) => (
        <NavLink key={t.to} to={t.to} end={t.end} className={({ isActive }) => (isActive ? "is-active" : undefined)}>
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
