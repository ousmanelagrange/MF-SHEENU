// Bandeau du site web quand la connexion tombe : les pages déjà ouvertes restent lisibles,
// mais rien ne peut être enregistré avant le retour du réseau (l'application mobile, elle,
// garde les envois en attente).

import { useEffect, useState } from "react";

export function OfflineBanner() {
  const [offline, setOffline] = useState(!navigator.onLine);
  useEffect(() => {
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  if (!offline) return null;
  return (
    <div className="offline-banner" role="alert">
      Hors connexion : vous pouvez lire ce qui est affiché, mais vos modifications ne seront pas enregistrées avant le retour du réseau.
    </div>
  );
}
