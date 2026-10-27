import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { api, session } from "../api";
import { s } from "../components/ui";
import { colors, fonts } from "../theme";
import { ROLE_LABELS, type MyFamily } from "../types";

export function FamiliesScreen({ onPick, onLogout }: { onPick: (f: MyFamily) => void; onLogout: () => void }) {
  const [items, setItems] = useState<MyFamily[] | null>(null);
  useEffect(() => {
    api<MyFamily[]>("/families").then(setItems).catch(() => setItems([]));
  }, []);

  return (
    <ScrollView style={{ backgroundColor: colors.cotton }} contentContainerStyle={{ paddingBottom: 40 }}>
      <Text style={[s.lead, { padding: 20 }]}>
        Un compte peut appartenir à deux familles. Elles restent séparées : aucune ne voit l'autre.
      </Text>
      {!items && <ActivityIndicator style={{ marginTop: 24 }} />}
      {items?.map((f) => (
        <Pressable
          key={f.id}
          onPress={async () => {
            await session.setFamily(f.id);
            onPick(f);
          }}
          style={({ pressed }) => [s.row, pressed && { backgroundColor: colors.indigo50 }]}
        >
          <View style={{ flex: 1 }}>
            <Text style={[s.name, { fontSize: 18 }]}>{f.name}</Text>
            <Text style={s.sub}>{[f.community, ROLE_LABELS[f.role]].filter(Boolean).join(", ")}</Text>
          </View>
          <Text style={s.meta}>Ouvrir</Text>
        </Pressable>
      ))}
      {items?.length === 0 && (
        <Text style={[s.lead, { padding: 20 }]}>
          Vous n'appartenez encore à aucune famille. Ouvrez le lien d'invitation reçu sur WhatsApp.
        </Text>
      )}
      <Pressable onPress={onLogout} style={{ padding: 20 }}>
        <Text style={{ fontFamily: fonts.uiMedium, color: colors.indigo500 }}>Se déconnecter</Text>
      </Pressable>
    </ScrollView>
  );
}
