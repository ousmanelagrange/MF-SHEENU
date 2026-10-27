// Mémoire de la famille sur mobile : récits, albums et frise, choisis en haut de l'écran.

import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Image, Pressable, Text, View } from "react-native";
import { api } from "../api";
import { Avatar, s, Segmented } from "../components/ui";
import { KIND_LABEL, when, type AlbumCard, type NarrativeCard, type TimelineItem } from "../memory";
import { colors, fonts } from "../theme";

type View3 = "narratives" | "albums" | "timeline";

export function MemoryScreen({
  onOpenNarrative,
  onOpenAlbum,
}: {
  onOpenNarrative: (id: string) => void;
  onOpenAlbum: (id: string) => void;
}) {
  const [view, setView] = useState<View3>("narratives");
  return (
    <View style={{ flex: 1, backgroundColor: colors.cotton }}>
      <Segmented
        value={view}
        onChange={setView}
        options={[
          ["narratives", "Récits"],
          ["albums", "Albums"],
          ["timeline", "Frise"],
        ]}
      />
      {view === "narratives" && <Narratives onOpen={onOpenNarrative} />}
      {view === "albums" && <Albums onOpen={onOpenAlbum} />}
      {view === "timeline" && <Timeline onOpenNarrative={onOpenNarrative} onOpenAlbum={onOpenAlbum} />}
    </View>
  );
}

function Narratives({ onOpen }: { onOpen: (id: string) => void }) {
  const [items, setItems] = useState<NarrativeCard[] | null>(null);
  useEffect(() => void api<NarrativeCard[]>("/narratives").then(setItems), []);
  if (!items) return <ActivityIndicator style={{ marginTop: 24 }} />;
  return (
    <FlatList
      data={items}
      keyExtractor={(n) => n.id}
      ListEmptyComponent={<Text style={[s.lead, { padding: 20 }]}>Aucun récit pour l'instant.</Text>}
      renderItem={({ item: n }) => (
        <Pressable
          onPress={() => onOpen(n.id)}
          style={({ pressed }) => [s.row, { alignItems: "flex-start" }, pressed && { backgroundColor: colors.indigo50 }]}
        >
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={[s.name, { fontSize: 17 }]}>{n.title}</Text>
            {n.teller && (
              <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                <Avatar person={n.teller} size={20} />
                <Text style={s.sub}>{n.teller.display_name}</Text>
              </View>
            )}
            <Text style={s.sub}>
              {[when(n), n.language, n.media_kind === "audio" ? "audio" : n.media_kind === "video" ? "vidéo" : null]
                .filter(Boolean)
                .join(", ")}
            </Text>
          </View>
          <Text style={[s.meta, { color: n.layers.length ? colors.indigo700 : colors.muted }]}>
            {n.layers.length ? n.layers.map((l) => (l === "original" ? "Texte" : l.toUpperCase())).join(" ") : "Sans texte"}
          </Text>
        </Pressable>
      )}
    />
  );
}

function Albums({ onOpen }: { onOpen: (id: string) => void }) {
  const [items, setItems] = useState<AlbumCard[] | null>(null);
  useEffect(() => void api<AlbumCard[]>("/albums").then(setItems), []);
  if (!items) return <ActivityIndicator style={{ marginTop: 24 }} />;
  return (
    <FlatList
      data={items}
      numColumns={2}
      keyExtractor={(a) => a.id}
      contentContainerStyle={{ paddingHorizontal: 14, gap: 18 }}
      columnWrapperStyle={{ gap: 12 }}
      ListEmptyComponent={<Text style={[s.lead, { padding: 6 }]}>Aucun album pour l'instant.</Text>}
      renderItem={({ item: a }) => (
        <Pressable onPress={() => onOpen(a.id)} style={{ flex: 1 / 2 }}>
          <View style={{ aspectRatio: 4 / 3, borderRadius: 4, overflow: "hidden", backgroundColor: colors.indigo50 }}>
            {a.cover_url && <Image source={{ uri: a.cover_url }} style={{ width: "100%", height: "100%" }} />}
          </View>
          <Text style={[s.name, { marginTop: 6, fontSize: 15 }]} numberOfLines={2}>
            {a.title}
          </Text>
          <Text style={s.sub}>
            {[a.year, a.count ? `${a.count} photo${a.count > 1 ? "s" : ""}` : "aucune photo"].filter(Boolean).join(", ")}
          </Text>
        </Pressable>
      )}
    />
  );
}

function Timeline({ onOpenNarrative, onOpenAlbum }: { onOpenNarrative: (id: string) => void; onOpenAlbum: (id: string) => void }) {
  const [items, setItems] = useState<TimelineItem[] | null>(null);
  useEffect(() => void api<TimelineItem[]>("/timeline").then(setItems), []);
  if (!items) return <ActivityIndicator style={{ marginTop: 24 }} />;
  const open = (i: TimelineItem) => {
    if (i.kind === "narrative" && i.ref_id) onOpenNarrative(i.ref_id);
    if ((i.kind === "album" || i.kind === "photo") && i.ref_id) onOpenAlbum(i.ref_id);
  };
  return (
    <FlatList
      data={items}
      keyExtractor={(i, k) => `${i.kind}-${i.ref_id}-${k}`}
      initialNumToRender={40}
      renderItem={({ item: i, index }) => {
        const decade = Math.floor(i.year / 10) * 10;
        const first = index === 0 || Math.floor(items[index - 1].year / 10) * 10 !== decade;
        const memory = i.kind === "narrative" || i.kind === "album" || i.kind === "photo";
        return (
          <View>
            {first && (
              <Text
                style={{
                  fontFamily: fonts.nameRegular,
                  fontSize: 24,
                  color: colors.indigo500,
                  paddingHorizontal: 20,
                  paddingTop: 18,
                  paddingBottom: 4,
                }}
              >
                {decade}
              </Text>
            )}
            <Pressable onPress={() => open(i)} style={{ flexDirection: "row", gap: 12, paddingHorizontal: 20, paddingVertical: 6 }}>
              <Text style={{ fontFamily: fonts.ui, color: colors.muted, width: 40 }}>{i.year}</Text>
              <View style={{ flex: 1 }}>
                <Text style={{ fontFamily: memory ? fonts.name : fonts.ui, fontSize: 15, color: colors.indigo900 }}>{i.title}</Text>
                {/* « Naissance de… » se suffit ; on n'étiquette que les récits, albums et annonces */}
                {(memory || i.kind === "life_event") && (
                  <Text style={{ fontFamily: fonts.uiSemi, fontSize: 12, color: colors.brass }}>{KIND_LABEL[i.kind]}</Text>
                )}
              </View>
            </Pressable>
          </View>
        );
      }}
    />
  );
}
