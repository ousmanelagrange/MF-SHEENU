import { InstrumentSans_400Regular, InstrumentSans_500Medium, InstrumentSans_600SemiBold } from "@expo-google-fonts/instrument-sans";
import { Literata_400Regular, Literata_500Medium, useFonts } from "@expo-google-fonts/literata";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { session } from "./src/api";
import { Mark } from "./src/components/ui";
import { FamiliesScreen } from "./src/screens/FamiliesScreen";
import { LoginScreen } from "./src/screens/LoginScreen";
import { PeopleScreen } from "./src/screens/PeopleScreen";
import { PersonScreen } from "./src/screens/PersonScreen";
import { colors, fonts } from "./src/theme";
import type { MyFamily } from "./src/types";

type Routes = {
  Families: undefined;
  People: undefined;
  Person: { id: string };
};

const Stack = createNativeStackNavigator<Routes>();

const navTheme = {
  ...DefaultTheme,
  colors: { ...DefaultTheme.colors, primary: colors.indigo700, background: colors.cotton, card: colors.white, text: colors.indigo900, border: colors.line },
};

export default function App() {
  const [loaded] = useFonts({
    Literata_400Regular,
    Literata_500Medium,
    InstrumentSans_400Regular,
    InstrumentSans_500Medium,
    InstrumentSans_600SemiBold,
  });
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [family, setFamily] = useState<MyFamily | null>(null);

  useEffect(() => {
    session.load().then((c) => {
      setAuthed(!!c.access);
      setReady(true);
    });
  }, []);

  if (!loaded || !ready) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.indigo700 }}>
        <Mark size={64} inverted />
        <ActivityIndicator color="#fff" style={{ marginTop: 24 }} />
      </View>
    );
  }

  const logout = async () => {
    await session.clear();
    setFamily(null);
    setAuthed(false);
  };

  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      {!authed ? (
        <LoginScreen onLoggedIn={() => setAuthed(true)} />
      ) : (
        <NavigationContainer theme={navTheme}>
          <Stack.Navigator
            screenOptions={{
              headerTitleStyle: { fontFamily: fonts.name, fontSize: 18, color: colors.indigo900 },
              headerTintColor: colors.indigo700,
              headerShadowVisible: false,
            }}
          >
            <Stack.Screen name="Families" options={{ title: "Vos familles" }}>
              {({ navigation }) => (
                <FamiliesScreen
                  onLogout={logout}
                  onPick={(f) => {
                    setFamily(f);
                    navigation.navigate("People");
                  }}
                />
              )}
            </Stack.Screen>
            <Stack.Screen
              name="People"
              options={({ navigation }) => ({
                title: family?.name ?? "Personnes",
                headerRight: () =>
                  family?.person_id ? (
                    <Pressable onPress={() => navigation.navigate("Person", { id: family.person_id! })}>
                      <Text style={{ fontFamily: fonts.uiMedium, color: colors.indigo500 }}>Ma fiche</Text>
                    </Pressable>
                  ) : null,
              })}
            >
              {({ navigation }) => <PeopleScreen onOpen={(id) => navigation.push("Person", { id })} />}
            </Stack.Screen>
            <Stack.Screen name="Person" options={{ title: "" }}>
              {({ route, navigation }) => (
                <PersonScreen id={route.params.id} meId={family?.person_id ?? null} onOpen={(id) => navigation.push("Person", { id })} />
              )}
            </Stack.Screen>
          </Stack.Navigator>
        </NavigationContainer>
      )}
    </SafeAreaProvider>
  );
}
