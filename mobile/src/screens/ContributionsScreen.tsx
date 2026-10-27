// Collectes de la famille sur mobile : avancement de chacune et ma situation.

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { api } from "../api";
import { s } from "../components/ui";
import { money } from "../money";
import { colors, fonts } from "../theme";
import type { ContributionEvent } from "../types";

export function ProgressBar({ event }: { event: ContributionEvent }) {
  const target = event.target_amount || event.totals.due;
  const ratio = target ? Math.min(1, event.totals.collected / target) : 0;
  return (
    <View style={{ gap: 6 }}>
      <Text style={{ fontFamily: fonts.ui, color: colors.muted, fontSize: 13.5 }}>
        <Text style={{ fontFamily: fonts.name, color: colors.indigo900, fontSize: 16 }}>{money(event.totals.collected, event.currency)}</Text>
        {target ? `  sur ${money(target, event.currency)}, ${Math.round(ratio * 100)} %` : ""}
      </Text>
      <View style={{ height: 6, backgroundColor: colors.indigo100, borderRadius: 3, overflow: "hidden" }}>
        <View style={{ width: `${ratio * 100}%`, height: "100%", backgroundColor: colors.brass }} />
      </View>
    </View>
  );
}

export function ContributionsScreen({ onOpen }: { onOpen: (id: string) => void }) {
  const [events, setEvents] = useState<ContributionEvent[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setEvents(await api<ContributionEvent[]>("/contributions/events"));
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  if (!events) return <ActivityIndicator style={{ marginTop: 40 }} />;
  const open = events.filter((e) => e.status === "open");
  const closed = events.filter((e) => e.status === "closed");

  return (
    <ScrollView
      style={{ backgroundColor: colors.cotton }}
      contentContainerStyle={{ paddingBottom: 40 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
    >
      {events.length === 0 && <Text style={[s.lead, { padding: 20 }]}>Aucune collecte pour l'instant.</Text>}
      {[["En cours", open], ["Clôturées", closed]].map(([title, list]) =>
        (list as ContributionEvent[]).length ? (
          <View key={title as string}>
            <Text style={s.section}>{title as string}</Text>
            {(list as ContributionEvent[]).map((e) => (
              <Pressable key={e.id} onPress={() => onOpen(e.id)} style={({ pressed }) => [s.row, { flexDirection: "column", alignItems: "stretch", gap: 10 }, pressed && { backgroundColor: colors.indigo50 }]}>
                <View>
                  <Text style={[s.name, { fontSize: 17 }]}>{e.title}</Text>
                  {e.deadline && <Text style={s.sub}>Échéance le {new Date(e.deadline).toLocaleDateString("fr-FR")}</Text>}
                </View>
                <ProgressBar event={e} />
              </Pressable>
            ))}
          </View>
        ) : null,
      )}
    </ScrollView>
  );
}
