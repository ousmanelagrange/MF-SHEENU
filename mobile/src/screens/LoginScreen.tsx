import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { api, session } from "../api";
import { Button, Field, Mark, s } from "../components/ui";
import { colors, fonts } from "../theme";

export function LoginScreen({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const t = await api<{ access_token: string; refresh_token: string }>("/auth/login", {
        method: "POST",
        body: { login, password },
      });
      await session.setTokens(t.access_token, t.refresh_token);
      onLoggedIn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.white }}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 24, paddingTop: 48 }} keyboardShouldPersistTaps="handled">
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <Mark size={34} />
            <Text style={{ fontFamily: fonts.name, fontSize: 22, color: colors.indigo900 }}>Sheenu</Text>
          </View>
          <Text style={[s.h1, { marginTop: 40 }]}>Se connecter</Text>
          <Text style={[s.lead, { marginTop: 6, marginBottom: 28 }]}>
            Avec l'e-mail ou le numéro de téléphone utilisé à l'inscription.
          </Text>
          {error && <Text style={s.error}>{error}</Text>}
          <Field label="E-mail ou téléphone" value={login} onChangeText={setLogin} autoCapitalize="none" autoComplete="username" />
          <Field label="Mot de passe" value={password} onChangeText={setPassword} secureTextEntry autoComplete="current-password" />
          <Button title={busy ? "Connexion…" : "Se connecter"} onPress={submit} disabled={busy || !login || !password} />
          <Text style={[s.lead, { marginTop: 24, fontSize: 14 }]}>
            Pas encore de compte ? Ouvrez le lien d'invitation reçu sur WhatsApp pour vous inscrire.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
