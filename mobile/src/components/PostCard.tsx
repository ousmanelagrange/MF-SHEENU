// Une publication du fil : auteur, texte, photo, sondage, réactions et accès aux commentaires.
// Les annonces du bureau gardent le même fond laiton que sur le web.

import { Image, Pressable, Text, View } from "react-native";
import { isQueued, send } from "../sync";
import { ago, kindLabel, REACTIONS, toggleReaction, type Author, type Post } from "../social";
import { colors, fonts } from "../theme";
import { Avatar } from "./ui";

export function AuthorAvatar({ author, size = 40 }: { author: Author; size?: number }) {
  if (author.person) return <Avatar person={author.person} size={size} />;
  const initials = author.name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("");
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: colors.indigo100,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Text style={{ fontFamily: fonts.name, fontSize: size * 0.38, color: colors.indigo700 }}>{initials}</Text>
    </View>
  );
}

export function PostCard({ post, onChange, onOpen }: { post: Post; onChange: (p: Post) => void; onOpen?: () => void }) {
  const label = kindLabel(post);
  const announcement = post.kind === "announcement";
  const totalVotes = post.poll?.reduce((n, o) => n + o.votes, 0) ?? 0;

  const react = async (key: string) => {
    const removing = post.my_reaction === key;
    if (post.pending) return;
    onChange(toggleReaction(post, key)); // affichage immédiat ; sans réseau, l'envoi attend
    await send(`/posts/${post.id}/reaction`, {
      method: removing ? "DELETE" : "PUT",
      body: removing ? undefined : { emoji: key },
      label: removing ? "Retrait d'une réaction" : "Réaction à une publication",
    }).catch(() => undefined);
  };
  const vote = async (optionId: string) => {
    if (post.pending || !post.poll) return;
    const r = await send<Post>(`/posts/${post.id}/vote`, { method: "POST", body: { option_id: optionId }, label: "Vote à un sondage" });
    if (!isQueued(r)) return onChange(r);
    // Hors connexion : le vote s'affiche tout de suite et partira au retour du réseau
    const poll = post.poll.map((o) => ({
      ...o,
      votes: o.votes + (o.id === optionId ? 1 : 0) - (o.id === post.my_vote ? 1 : 0),
    }));
    onChange({ ...post, poll, my_vote: optionId });
  };

  return (
    <View
      style={{
        backgroundColor: announcement ? colors.brassSoft : colors.white,
        borderLeftWidth: announcement ? 3 : 0,
        borderLeftColor: colors.brass,
        paddingHorizontal: 20,
        paddingVertical: 16,
        borderBottomWidth: 1,
        borderBottomColor: colors.line,
      }}
    >
      <View style={{ flexDirection: "row", gap: 10, alignItems: "center" }}>
        <AuthorAvatar author={post.author} size={36} />
        <View style={{ flex: 1 }}>
          <Text style={{ fontFamily: fonts.name, fontSize: 15, color: colors.indigo700 }}>{post.author.name}</Text>
          <Text style={{ fontFamily: fonts.ui, fontSize: 12.5, color: post.pending ? colors.brass : colors.muted }}>
            {post.pending ? "En attente d'envoi" : `${label ? `${label}, ` : ""}${ago(post.created_at)}`}
          </Text>
        </View>
      </View>

      {!!post.text && (
        <Text style={{ fontFamily: fonts.ui, fontSize: 15.5, lineHeight: 22, color: colors.indigo900, marginTop: 10 }}>{post.text}</Text>
      )}
      {post.media[0] && (
        <Image
          source={{ uri: post.media[0] }}
          style={{ width: "100%", aspectRatio: 4 / 3, borderRadius: 8, marginTop: 10, backgroundColor: colors.indigo50 }}
        />
      )}

      {post.poll && (
        <View style={{ marginTop: 10, gap: 6 }}>
          {post.poll.map((o) => {
            const share = totalVotes ? o.votes / totalVotes : 0;
            const mine = post.my_vote === o.id;
            return (
              <Pressable
                key={o.id}
                onPress={() => vote(o.id)}
                style={{
                  borderWidth: 1,
                  borderColor: mine ? colors.indigo700 : colors.line,
                  borderRadius: 6,
                  overflow: "hidden",
                  backgroundColor: colors.white,
                }}
              >
                <View
                  style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${share * 100}%`, backgroundColor: colors.indigo50 }}
                />
                <View style={{ flexDirection: "row", justifyContent: "space-between", padding: 10 }}>
                  <Text style={{ fontFamily: mine ? fonts.uiSemi : fonts.ui, color: colors.indigo900 }}>{o.label}</Text>
                  <Text style={{ fontFamily: fonts.ui, color: colors.muted }}>{o.votes}</Text>
                </View>
              </Pressable>
            );
          })}
        </View>
      )}

      <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 12 }}>
        {REACTIONS.map((r) => {
          const n = post.reactions[r.key] ?? 0;
          const mine = post.my_reaction === r.key;
          return (
            <Pressable
              key={r.key}
              onPress={() => react(r.key)}
              accessibilityLabel={`Réagir ${r.key}`}
              style={{
                flexDirection: "row",
                gap: 4,
                paddingHorizontal: 9,
                paddingVertical: 4,
                borderRadius: 14,
                borderWidth: 1,
                borderColor: mine ? colors.indigo700 : colors.line,
                backgroundColor: mine ? colors.indigo50 : colors.white,
              }}
            >
              <Text>{r.emoji}</Text>
              {n > 0 && <Text style={{ fontFamily: fonts.uiMedium, fontSize: 12.5, color: colors.indigo900 }}>{n}</Text>}
            </Pressable>
          );
        })}
        <View style={{ flex: 1 }} />
        {onOpen && !post.pending && (
          <Pressable onPress={onOpen} hitSlop={8}>
            <Text style={{ fontFamily: fonts.uiMedium, fontSize: 14, color: colors.indigo700 }}>
              {post.comments_count ? `${post.comments_count} commentaire${post.comments_count > 1 ? "s" : ""}` : "Commenter"}
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}
