// Point d'entrée mobile : charge les polices et la session, puis affiche
// la connexion ou la navigation de l'application.

import { InstrumentSans_400Regular, InstrumentSans_500Medium, InstrumentSans_600SemiBold } from "@expo-google-fonts/instrument-sans";
import { Literata_400Regular, Literata_500Medium, useFonts } from "@expo-google-fonts/literata";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { session } from "./src/api";
import { Mark } from "./src/components/ui";
import { AppNavigation } from "./src/navigation";
import { LoginScreen } from "./src/screens/LoginScreen";
import { colors } from "./src/theme";

export default function App() {
  const [fontsLoaded] = useFonts({
    Literata_400Regular,
    Literata_500Medium,
    InstrumentSans_400Regular,
    InstrumentSans_500Medium,
    InstrumentSans_600SemiBold,
  });
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    session.load().then((c) => {
      setAuthed(!!c.access);
      setReady(true);
    });
  }, []);

  if (!fontsLoaded || !ready) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.indigo700 }}>
        <Mark size={64} inverted />
        <ActivityIndicator color="#fff" style={{ marginTop: 24 }} />
      </View>
    );
  }

  const logout = async () => {
    await session.clear();
    setAuthed(false);
  };

  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      {authed ? <AppNavigation onLogout={logout} /> : <LoginScreen onLoggedIn={() => setAuthed(true)} />}
    </SafeAreaProvider>
  );
}
