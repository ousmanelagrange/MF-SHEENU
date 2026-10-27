// Une publication ouverte avec ses commentaires, et un champ pour répondre.

import { useEffect, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { api } from "../api";
import { AuthorAvatar, PostCard } from "../components/PostCard";
import { s } from "../components/ui";
import { ago, type CommentItem, type Post } from "../social";
import { colors, fonts } from "../theme";

export function PostScreen({ id }: { id: string }) {
  const [post, setPost] = useState<Post | null>(null);
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [text, setText] = useState("");

  useEffect(() => {
    void api<Post>(`/posts/${id}`).then(setPost);
    void api<CommentItem[]>(`/posts/${id}/comments`).then(setComments);
  }, [id]);

  const send = async () => {
    const c = await api<CommentItem>(`/posts/${id}/comments`, { method: "POST", body: { text } });
    setComments([...comments, c]);
    setText("");
  };

  if (!post) return <ActivityIndicator style={{ marginTop: 40 }} />;
  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: colors.cotton }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView>
        <PostCard post={post} onChange={setPost} />
        <Text style={s.section}>{comments.length ? "Commentaires" : "Aucun commentaire pour l'instant"}</Text>
        {comments.map((c) => (
          <View key={c.id} style={{ flexDirection: "row", gap: 10, paddingHorizontal: 20, paddingVertical: 10 }}>
            <AuthorAvatar author={c.author} size={30} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontFamily: fonts.name, fontSize: 14, color: colors.indigo900 }}>
                {c.author.name} <Text style={{ fontFamily: fonts.ui, fontSize: 12.5, color: colors.muted }}>{ago(c.created_at)}</Text>
              </Text>
              <Text style={{ fontFamily: fonts.ui, fontSize: 15, lineHeight: 21, color: colors.indigo900, marginTop: 2 }}>{c.text}</Text>
            </View>
          </View>
        ))}
      </ScrollView>
      <View style={{ flexDirection: "row", gap: 8, padding: 12, borderTopWidth: 1, borderTopColor: colors.line, backgroundColor: colors.white }}>
        <TextInput value={text} onChangeText={setText} placeholder="Votre commentaire" placeholderTextColor={colors.muted} style={[s.input, { flex: 1, paddingVertical: 9 }]} />
        <Pressable onPress={send} disabled={!text.trim()} style={{ justifyContent: "center", paddingHorizontal: 8, opacity: text.trim() ? 1 : 0.4 }}>
          <Text style={{ fontFamily: fonts.uiSemi, color: colors.indigo700 }}>Envoyer</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}
