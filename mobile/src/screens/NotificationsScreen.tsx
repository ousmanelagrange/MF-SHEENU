// Notifications du membre : annonces, commentaires, validations, rattachements.
// Ouvrir l'écran marque tout comme lu.

import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Text, View } from "react-native";
import { api } from "../api";
import { s } from "../components/ui";
import { ago } from "../social";
import { colors, fonts } from "../theme";

type Item = { id: string; title: string; body: string | null; read: boolean; created_at: string };

export function NotificationsScreen({ onRead }: { onRead: () => void }) {
  const [items, setItems] = useState<Item[] | null>(null);

  useEffect(() => {
    void api<{ items: Item[] }>("/notifications").then(async (page) => {
      setItems(page.items);
      if (page.items.some((n) => !n.read)) {
        await api("/notifications/read", { method: "POST", body: {} }).catch(() => undefined);
        onRead();
      }
    });
  }, [onRead]);

  if (!items) return <ActivityIndicator style={{ marginTop: 40 }} />;
  return (
    <FlatList
      style={{ backgroundColor: colors.cotton }}
      data={items}
      keyExtractor={(n) => n.id}
      ListEmptyComponent={<Text style={[s.lead, { padding: 20 }]}>Rien de nouveau.</Text>}
      renderItem={({ item: n }) => (
        <View style={[s.row, { alignItems: "flex-start" }]}>
          <View style={{ width: 8, height: 8, borderRadius: 4, marginTop: 7, backgroundColor: n.read ? "transparent" : colors.brass }} />
          <View style={{ flex: 1, gap: 3 }}>
            <Text style={{ fontFamily: n.read ? fonts.ui : fonts.uiSemi, fontSize: 15, color: colors.indigo900 }}>{n.title}</Text>
            {n.body && (
              <Text style={s.sub} numberOfLines={3}>
                {n.body}
              </Text>
            )}
            <Text style={[s.sub, { fontSize: 12 }]}>{ago(n.created_at)}</Text>
          </View>
        </View>
      )}
    />
  );
}
