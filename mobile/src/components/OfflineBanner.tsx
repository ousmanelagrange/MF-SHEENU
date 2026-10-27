// Bandeau affiché quand le téléphone n'a plus de réseau : on lit les dernières données reçues.
// Posé en bas de l'écran, au-dessus de la barre d'onglets, sans décaler les en-têtes.

import { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { onConnectivity } from "../api";
import { onOutbox } from "../sync";
import { colors, fonts } from "../theme";

export function OfflineBanner() {
  const [offline, setOffline] = useState(false);
  const [waiting, setWaiting] = useState(0);
  const insets = useSafeAreaInsets();
  useEffect(() => onConnectivity(setOffline), []);
  useEffect(() => onOutbox((q) => setWaiting(q.filter((i) => i.status === "pending").length)), []);
  if (!offline && waiting === 0) return null;
  return (
    <View
      accessibilityRole="alert"
      pointerEvents="none"
      style={{
        position: "absolute",
        left: 12,
        right: 12,
        bottom: insets.bottom + 72,
        zIndex: 10,
        backgroundColor: colors.brassSoft,
        borderRadius: 8,
        paddingHorizontal: 14,
        paddingVertical: 10,
      }}
    >
      <Text style={{ fontFamily: fonts.uiMedium, fontSize: 13, color: colors.indigo900 }}>
        {offline
          ? `Hors connexion : vous voyez les dernières données reçues.${waiting ? ` ${waiting} envoi(s) en attente.` : ""}`
          : `Synchronisation : ${waiting} envoi(s) en cours.`}
      </Text>
    </View>
  );
}
