// Fil de la famille sur mobile : stories en haut, champ de publication, puis les publications
// (annonces épinglées d'abord). Tirer vers le bas recharge ; la fin de liste charge les plus anciennes.

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Image, Modal, Pressable, RefreshControl, ScrollView, Text, TextInput, View } from "react-native";
import { api, uploadImage } from "../api";
import { AuthorAvatar, PostCard } from "../components/PostCard";
import { s } from "../components/ui";
import { ago, type Post, type StoryGroup } from "../social";
import { pickImages } from "../pickImages";
import { colors, fonts } from "../theme";

type Page = { items: Post[]; next_before: string | null };

export function FeedScreen({ onOpenPost }: { onOpenPost: (id: string) => void }) {
  const [posts, setPosts] = useState<Post[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [stories, setStories] = useState<StoryGroup[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (before?: string) => {
    const page = await api<Page>("/feed", { query: { before } });
    setPosts((prev) => (before ? [...(prev ?? []), ...page.items] : page.items));
    setNext(page.next_before);
  }, []);

  const reload = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([load(), api<StoryGroup[]>("/stories").then(setStories)]);
    setRefreshing(false);
  }, [load]);
  useEffect(() => void reload(), [reload]);

  const replace = (p: Post) => setPosts((list) => list?.map((x) => (x.id === p.id ? p : x)) ?? null);

  if (!posts) return <ActivityIndicator style={{ marginTop: 40 }} />;
  return (
    <FlatList
      style={{ backgroundColor: colors.cotton }}
      data={posts}
      keyExtractor={(p) => p.id}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} />}
      onEndReached={() => next && load(next)}
      ListHeaderComponent={
        <>
          <Stories groups={stories} />
          <Composer onPosted={(p) => setPosts([p, ...posts])} />
        </>
      }
      ListEmptyComponent={<Text style={[s.lead, { padding: 20 }]}>Rien pour l'instant. Partagez la première nouvelle de la famille.</Text>}
      renderItem={({ item }) => <PostCard post={item} onChange={replace} onOpen={() => onOpenPost(item.id)} />}
    />
  );
}

/** Bandeau des stories des dernières 24 heures ; un appui ouvre la visionneuse plein écran. */
function Stories({ groups }: { groups: StoryGroup[] }) {
  const [open, setOpen] = useState<{ g: number; i: number } | null>(null);
  if (groups.length === 0) return null;
  const current = open ? groups[open.g].stories[open.i] : null;
  const advance = () => {
    if (!open) return;
    if (open.i + 1 < groups[open.g].stories.length) setOpen({ ...open, i: open.i + 1 });
    else if (open.g + 1 < groups.length) setOpen({ g: open.g + 1, i: 0 });
    else setOpen(null);
  };

  return (
    <>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ gap: 14, paddingHorizontal: 20, paddingVertical: 14 }}
      >
        {groups.map((g, gi) => (
          <Pressable key={g.author.user_id} onPress={() => setOpen({ g: gi, i: 0 })} style={{ alignItems: "center", width: 64 }}>
            <View style={{ padding: 2, borderRadius: 32, borderWidth: 2, borderColor: colors.brass }}>
              <AuthorAvatar author={g.author} size={52} />
            </View>
            <Text numberOfLines={1} style={{ fontFamily: fonts.ui, fontSize: 12, color: colors.indigo900, marginTop: 4 }}>
              {g.author.name.split(" ")[0]}
            </Text>
          </Pressable>
        ))}
      </ScrollView>
      <Modal visible={!!current} animationType="fade" onRequestClose={() => setOpen(null)}>
        {current && open && (
          <Pressable onPress={advance} style={{ flex: 1, backgroundColor: colors.indigo900, justifyContent: "center" }}>
            <Image source={{ uri: current.media_url }} style={{ width: "100%", aspectRatio: 3 / 4 }} resizeMode="contain" />
            <View style={{ position: "absolute", top: 48, left: 20, right: 20 }}>
              <Text style={{ fontFamily: fonts.uiSemi, color: colors.white }}>
                {groups[open.g].author.name} <Text style={{ fontFamily: fonts.ui, opacity: 0.8 }}>{ago(current.created_at)}</Text>
              </Text>
            </View>
            {current.caption && (
              <Text
                style={{ position: "absolute", bottom: 48, left: 20, right: 20, fontFamily: fonts.ui, fontSize: 16, color: colors.white }}
              >
                {current.caption}
              </Text>
            )}
          </Pressable>
        )}
      </Modal>
    </>
  );
}

/** Publication rapide : un message, avec une photo si l'on veut. Annonces et sondages se font sur le web. */
function Composer({ onPosted }: { onPosted: (p: Post) => void }) {
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const empty = !text.trim() && !photo;
  const attach = async () => {
    const [asset] = await pickImages(false);
    if (!asset) return;
    setBusy(true);
    try {
      setPhoto(await uploadImage(asset));
    } finally {
      setBusy(false);
    }
  };
  const publish = async () => {
    setBusy(true);
    try {
      onPosted(await api<Post>("/posts", { method: "POST", body: { kind: "post", text, media: photo ? [photo] : [] } }));
      setText("");
      setPhoto(null);
    } finally {
      setBusy(false);
    }
  };
  return (
    <View style={{ paddingHorizontal: 20, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: colors.line, gap: 10 }}>
      <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-end" }}>
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder="Une nouvelle à partager avec la famille ?"
          placeholderTextColor={colors.muted}
          multiline
          style={[s.input, { flex: 1, maxHeight: 120, fontSize: 15 }]}
        />
        <Pressable
          onPress={publish}
          disabled={empty || busy}
          style={{
            backgroundColor: colors.indigo700,
            borderRadius: 6,
            paddingHorizontal: 14,
            paddingVertical: 12,
            opacity: empty || busy ? 0.5 : 1,
          }}
        >
          <Text style={{ fontFamily: fonts.uiSemi, color: colors.white }}>Publier</Text>
        </Pressable>
      </View>
      {photo ? (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          <Image source={{ uri: photo }} style={{ width: 64, height: 64, borderRadius: 6 }} />
          <Pressable onPress={() => setPhoto(null)} hitSlop={8}>
            <Text style={{ fontFamily: fonts.uiMedium, color: colors.muted }}>Retirer la photo</Text>
          </Pressable>
        </View>
      ) : (
        <Pressable onPress={attach} hitSlop={8} disabled={busy}>
          <Text style={{ fontFamily: fonts.uiMedium, color: colors.indigo700 }}>Ajouter une photo</Text>
        </Pressable>
      )}
    </View>
  );
}
