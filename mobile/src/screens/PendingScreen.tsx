// Envois en attente : ce qui a été fait sans réseau et n'est pas encore arrivé, et ce que
// le serveur a refusé au moment de la synchronisation (avec son motif).

import { useEffect, useState } from "react";
import { FlatList, Pressable, Text, View } from "react-native";
import { isOffline } from "../api";
import { Button, s } from "../components/ui";
import { ago } from "../social";
import { discard, flush, onOutbox, retry, type Pending } from "../sync";
import { colors, fonts } from "../theme";

export function PendingScreen() {
  const [items, setItems] = useState<Pending[]>([]);
  useEffect(() => onOutbox(setItems), []);

  return (
    <FlatList
      style={{ backgroundColor: colors.cotton }}
      data={items}
      keyExtractor={(i) => i.id}
      ListHeaderComponent={
        <View style={{ padding: 20, gap: 12 }}>
          <Text style={s.lead}>
            {items.length === 0
              ? "Tout est envoyé."
              : isOffline()
                ? "Pas de réseau pour l'instant. Ces envois partiront tout seuls, dans l'ordre, dès le retour de la connexion."
                : "Ces envois partent dans l'ordre. Ceux que le serveur a refusés restent ici avec leur motif."}
          </Text>
          {items.some((i) => i.status === "pending") && <Button title="Envoyer maintenant" kind="ghost" onPress={() => void flush()} />}
        </View>
      }
      renderItem={({ item }) => (
        <View style={[s.row, { flexDirection: "column", alignItems: "stretch", gap: 4 }]}>
          <Text style={{ fontFamily: fonts.uiMedium, fontSize: 15, color: colors.indigo900 }}>{item.label}</Text>
          <Text style={[s.sub, item.status === "failed" && { color: colors.camwood }]}>
            {item.status === "failed" ? `Refusé : ${item.error}` : `En attente depuis ${ago(item.createdAt).replace("il y a ", "")}`}
          </Text>
          <View style={{ flexDirection: "row", gap: 20, marginTop: 4 }}>
            {item.status === "failed" && (
              <Pressable onPress={() => void retry(item.id)} hitSlop={8}>
                <Text style={{ fontFamily: fonts.uiSemi, color: colors.indigo700 }}>Réessayer</Text>
              </Pressable>
            )}
            <Pressable onPress={() => void discard(item.id)} hitSlop={8}>
              <Text style={{ fontFamily: fonts.uiMedium, color: colors.muted }}>Abandonner</Text>
            </Pressable>
          </View>
        </View>
      )}
    />
  );
}
