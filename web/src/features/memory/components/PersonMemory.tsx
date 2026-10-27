// Sur la fiche d'une personne : les récits qui parlent d'elle (ou qu'elle a racontés),
// les photos où elle a été reconnue, et un lien vers sa frise.

import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../lib/api";
import type { AlbumPhoto, NarrativeCard } from "../../../types";
import { when } from "../format";

export function PersonMemory({ personId }: { personId: string }) {
  const [narratives, setNarratives] = useState<NarrativeCard[]>([]);
  const [photos, setPhotos] = useState<AlbumPhoto[]>([]);

  useEffect(() => {
    void api<NarrativeCard[]>("/narratives", { query: { person_id: personId } }).then(setNarratives);
    void api<AlbumPhoto[]>(`/persons/${personId}/photos`).then(setPhotos);
  }, [personId]);

  return (
    <section className="kin-group">
      <h2>
        Mémoire <Link to={`/memoire/frise?personne=${personId}`} className="h2-link">voir sa frise</Link>
      </h2>
      {narratives.length === 0 && photos.length === 0 && (
        <p className="empty-note" style={{ margin: 0 }}>Aucun récit ni photo pour l'instant.</p>
      )}
      {narratives.length > 0 && (
        <ul className="kin-list">
          {narratives.map((n) => (
            <li key={n.id}>
              <Link to={`/memoire/recits/${n.id}`} className="kin-item">
                <span className="pname">{n.title}</span>
                <span className="kin-meta">{when(n) ?? (n.teller?.id === personId ? "raconté par lui ou elle" : "")}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {photos.length > 0 && (
        <div className="photo-strip">
          {photos.slice(0, 8).map((p) => (
            <Link key={p.id} to={`/memoire/albums/${p.album_id}`} title={p.caption ?? undefined}>
              <img src={p.url} alt={p.caption ?? ""} loading="lazy" />
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
