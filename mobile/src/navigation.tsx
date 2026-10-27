// Navigation une fois connecté : choix de la famille, puis cinq onglets
// (Fil, Personnes, Arbre, Cotisations, Plus). Fiches, publications, collectes, mémoire et
// propositions s'ouvrent par-dessus les onglets ; mémoire et propositions depuis « Plus ».

import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { DefaultTheme, NavigationContainer, type NavigationProp } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { useCallback, useEffect, useState } from "react";
import { Platform, Pressable, ScrollView, Text } from "react-native";
import { api, session } from "./api";
import { FeedIcon, MoreIcon, PeopleIcon, TreeIcon, WalletIcon } from "./components/icons";
import { OfflineBanner } from "./components/OfflineBanner";
import { s } from "./components/ui";
import { AlbumScreen } from "./screens/AlbumScreen";
import { ContributionsScreen } from "./screens/ContributionsScreen";
import { EventScreen } from "./screens/EventScreen";
import { FamiliesScreen } from "./screens/FamiliesScreen";
import { DiasporaScreen } from "./screens/DiasporaScreen";
import { FeedScreen } from "./screens/FeedScreen";
import { MemoryScreen } from "./screens/MemoryScreen";
import { NarrativeScreen } from "./screens/NarrativeScreen";
import { NotificationsScreen } from "./screens/NotificationsScreen";
import { PeopleScreen } from "./screens/PeopleScreen";
import { PersonScreen } from "./screens/PersonScreen";
import { PostScreen } from "./screens/PostScreen";
import { ProposalsScreen } from "./screens/ProposalsScreen";
import { TreeScreen } from "./screens/TreeScreen";
import { colors, fonts } from "./theme";
import { ROLE_LABELS, type MyFamily } from "./types";

type RootRoutes = {
  Families: undefined;
  Main: undefined;
  Person: { id: string };
  Event: { id: string };
  Post: { id: string };
  Proposals: undefined;
  Memory: undefined;
  Narrative: { id: string };
  Album: { id: string };
  Notifications: undefined;
  Diaspora: undefined;
};
type Nav = NavigationProp<RootRoutes>;

const Stack = createNativeStackNavigator<RootRoutes>();
const Tabs = createBottomTabNavigator();

const theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: colors.indigo700,
    background: colors.cotton,
    card: colors.white,
    text: colors.indigo900,
    border: colors.line,
  },
};
const headerTitleStyle = { fontFamily: fonts.name, fontSize: 18, color: colors.indigo900 };

export function AppNavigation({ onLogout }: { onLogout: () => void }) {
  const [family, setFamily] = useState<MyFamily | null>(null);
  const [toReview, setToReview] = useState(0);
  const [unread, setUnread] = useState(0);

  // Compteurs de l'onglet « Plus » : propositions à valider et notifications non lues,
  // relus chaque minute tant que l'application est ouverte.
  const refreshCounts = useCallback(() => {
    if (!family) return;
    api<{ to_review: number }>("/proposals/counts")
      .then((c) => setToReview(c.to_review))
      .catch(() => undefined);
    api<{ unread: number }>("/notifications")
      .then((n) => setUnread(n.unread))
      .catch(() => undefined);
  }, [family]);
  const markRead = useCallback(() => setUnread(0), []);
  useEffect(() => {
    refreshCounts();
    const id = setInterval(refreshCounts, 60_000);
    return () => clearInterval(id);
  }, [refreshCounts]);

  return (
    <NavigationContainer theme={theme}>
      <Stack.Navigator screenOptions={{ headerTitleStyle, headerTintColor: colors.indigo700, headerShadowVisible: false }}>
        <Stack.Screen name="Families" options={{ title: "Vos familles" }}>
          {({ navigation }) => (
            <FamiliesScreen
              onLogout={onLogout}
              onPick={(f) => {
                setFamily(f);
                navigation.navigate("Main");
              }}
            />
          )}
        </Stack.Screen>
        <Stack.Screen name="Main" options={{ headerShown: false }}>
          {({ navigation }) => <MainTabs family={family} toReview={toReview} unread={unread} nav={navigation as unknown as Nav} onLogout={onLogout} />}
        </Stack.Screen>
        <Stack.Screen name="Event" options={{ title: "Collecte" }}>
          {({ route, navigation }) => (
            <EventScreen id={route.params.id} meId={family?.person_id ?? null} onOpenPerson={(id) => navigation.push("Person", { id })} />
          )}
        </Stack.Screen>
        <Stack.Screen name="Post" options={{ title: "Publication" }}>
          {({ route }) => <PostScreen id={route.params.id} />}
        </Stack.Screen>
        <Stack.Screen name="Memory" options={{ title: "Mémoire de la famille" }}>
          {({ navigation }) => (
            <MemoryScreen
              onOpenNarrative={(id) => navigation.push("Narrative", { id })}
              onOpenAlbum={(id) => navigation.push("Album", { id })}
            />
          )}
        </Stack.Screen>
        <Stack.Screen name="Narrative" options={{ title: "Récit" }}>
          {({ route, navigation }) => <NarrativeScreen id={route.params.id} onOpenPerson={(id) => navigation.push("Person", { id })} />}
        </Stack.Screen>
        <Stack.Screen name="Album" options={{ title: "Album" }}>
          {({ route }) => <AlbumScreen id={route.params.id} />}
        </Stack.Screen>
        <Stack.Screen name="Notifications" options={{ title: "Notifications" }}>
          {() => <NotificationsScreen onRead={markRead} />}
        </Stack.Screen>
        <Stack.Screen name="Diaspora" options={{ title: "La famille dans le monde" }}>
          {({ navigation }) => <DiasporaScreen onOpenPerson={(id) => navigation.push("Person", { id })} />}
        </Stack.Screen>
        <Stack.Screen name="Proposals" options={{ title: "Propositions" }}>
          {() => <ProposalsScreen />}
        </Stack.Screen>
        <Stack.Screen name="Person" options={{ title: "" }}>
          {({ route, navigation }) => (
            <PersonScreen id={route.params.id} meId={family?.person_id ?? null} onOpen={(id) => navigation.push("Person", { id })} />
          )}
        </Stack.Screen>
      </Stack.Navigator>
      <OfflineBanner />
    </NavigationContainer>
  );
}

function MainTabs({
  family,
  toReview,
  unread,
  nav,
  onLogout,
}: {
  family: MyFamily | null;
  toReview: number;
  unread: number;
  nav: Nav;
  onLogout: () => void;
}) {
  const open = (id: string) => nav.navigate("Person", { id });
  return (
    <Tabs.Navigator
      screenOptions={{
        headerTitleStyle,
        headerShadowVisible: false,
        tabBarActiveTintColor: colors.indigo700,
        tabBarInactiveTintColor: colors.muted,
        tabBarLabelStyle: { fontFamily: fonts.uiMedium, fontSize: 11.5, lineHeight: 15 },
        // Sur le web (pas de zone de sécurité en bas), on laisse de la place aux libellés.
        tabBarStyle: Platform.OS === "web" ? { height: 62, paddingBottom: 8 } : undefined,
      }}
    >
      <Tabs.Screen name="Fil" options={{ title: family?.name ?? "Fil", tabBarLabel: "Fil", tabBarIcon: FeedIcon }}>
        {() => <FeedScreen onOpenPost={(id) => nav.navigate("Post", { id })} />}
      </Tabs.Screen>
      <Tabs.Screen name="Personnes" options={{ tabBarIcon: PeopleIcon }}>
        {() => <PeopleScreen onOpen={open} />}
      </Tabs.Screen>
      <Tabs.Screen name="Arbre" options={{ tabBarIcon: TreeIcon }}>
        {() => <TreeScreen onOpen={open} />}
      </Tabs.Screen>
      <Tabs.Screen name="Cotisations" options={{ tabBarIcon: WalletIcon }}>
        {() => <ContributionsScreen onOpen={(id) => nav.navigate("Event", { id })} />}
      </Tabs.Screen>
      <Tabs.Screen
        name="Plus"
        options={{
          tabBarIcon: MoreIcon,
          tabBarBadge: toReview + unread > 0 ? toReview + unread : undefined,
          tabBarBadgeStyle: { backgroundColor: colors.brass },
        }}
      >
        {() => (
          <ScrollView style={{ backgroundColor: colors.cotton }}>
            <Text style={[s.lead, { padding: 20 }]}>
              {family?.name}, {ROLE_LABELS[family?.role ?? "member"]?.toLowerCase()}
            </Text>
            <MenuRow label="Notifications" count={unread} countLabel="nouvelle(s)" onPress={() => nav.navigate("Notifications")} />
            {family?.person_id && <MenuRow label="Ma fiche" onPress={() => open(family.person_id!)} />}
            <MenuRow label="Mémoire de la famille" onPress={() => nav.navigate("Memory")} />
            <MenuRow label="La famille dans le monde" onPress={() => nav.navigate("Diaspora")} />
            <MenuRow label="Propositions" count={toReview} onPress={() => nav.navigate("Proposals")} />
            <MenuRow
              label="Changer de famille"
              onPress={async () => {
                await session.setFamily(null);
                nav.navigate("Families");
              }}
            />
            <MenuRow label="Se déconnecter" onPress={onLogout} />
          </ScrollView>
        )}
      </Tabs.Screen>
    </Tabs.Navigator>
  );
}

function MenuRow({ label, count, countLabel = "à valider", onPress }: { label: string; count?: number; countLabel?: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [s.row, pressed && { backgroundColor: colors.indigo50 }]}>
      <Text style={[s.name, { fontFamily: fonts.uiMedium, fontSize: 16, flex: 1 }]}>{label}</Text>
      {!!count && (
        <Text style={[s.meta, { color: colors.brass, fontFamily: fonts.uiSemi }]}>
          {count} {countLabel}
        </Text>
      )}
    </Pressable>
  );
}
