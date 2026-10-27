// Fil de la famille : stories, zone de rédaction, publications (annonces épinglées d'abord),
// et dans la colonne de droite les anniversaires à venir.

import { Button, Segmented, Spin } from "antd";
import { useCallback, useEffect, useState } from "react";
import { PageHead } from "../../components/AppShell";
import { api } from "../../lib/api";
import { useFamily } from "../../lib/family";
import type { PersonSummary, Post } from "../../types";
import { Birthdays } from "./components/Birthdays";
import { Composer } from "./components/Composer";
import { PostCard } from "./components/PostCard";
import { StoriesBar } from "./components/StoriesBar";

type Page = { items: Post[]; next_before: string | null };

export function FeedPage() {
  const { family } = useFamily();
  const [me, setMe] = useState<PersonSummary | null>(null);
  const [posts, setPosts] = useState<Post[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [kind, setKind] = useState<string>("all");

  const load = useCallback(
    async (before?: string) => {
      const page = await api<Page>("/feed", { query: { before, kind: kind === "all" ? undefined : kind } });
      setPosts((prev) => (before ? [...(prev ?? []), ...page.items] : page.items));
      setNext(page.next_before);
    },
    [kind],
  );

  useEffect(() => {
    setPosts(null);
    void load();
  }, [load]);
  useEffect(() => {
    if (family?.person_id) void api<PersonSummary>(`/persons/${family.person_id}`).then(setMe);
  }, [family?.person_id]);

  const replace = (p: Post) => setPosts((list) => list?.map((x) => (x.id === p.id ? p : x)) ?? null);

  return (
    <div className="page feed-layout">
      <div className="feed-main">
        <PageHead title="Fil de la famille" />
        <StoriesBar me={me} />
        <Composer me={me} onPosted={(p) => setPosts((list) => [p, ...(list ?? [])])} />
        <Segmented
          value={kind}
          onChange={(v) => setKind(String(v))}
          options={[
            { label: "Tout", value: "all" },
            { label: "Annonces", value: "announcement" },
            { label: "Annonces de vie", value: "life_event" },
            { label: "Sondages", value: "poll" },
          ]}
          style={{ margin: "8px 0 4px" }}
        />
        {!posts ? (
          <Spin style={{ display: "block", margin: 32 }} />
        ) : posts.length === 0 ? (
          <p className="empty-note">Rien pour l'instant. Partagez la première nouvelle de la famille.</p>
        ) : (
          posts.map((p) => (
            <PostCard key={p.id} post={p} onChange={replace} onRemove={() => setPosts(posts.filter((x) => x.id !== p.id))} />
          ))
        )}
        {next && (
          <Button block onClick={() => load(next)} style={{ marginTop: 16 }}>
            Voir les publications plus anciennes
          </Button>
        )}
      </div>
      <aside className="feed-side">
        <Birthdays />
      </aside>
    </div>
  );
}
