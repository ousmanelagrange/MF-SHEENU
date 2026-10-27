// Où vit la famille, pays par pays. Toucher un pays affiche les personnes qui y vivent.

import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { api } from "../api";
import { PersonRow, s } from "../components/ui";
import { colors, fonts } from "../theme";
import type { PersonSummary } from "../types";

type Diaspora = { countries: { country: string; count: number }[]; unknown: number; living: number };

export function DiasporaScreen({ onOpenPerson }: { onOpenPerson: (id: string) => void }) {
  const [data, setData] = useState<Diaspora | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [people, setPeople] = useState<PersonSummary[]>([]);

  useEffect(() => void api<Diaspora>("/diaspora").then(setData), []);
  useEffect(() => {
    if (!open) return setPeople([]);
    void api<{ items: PersonSummary[] }>("/persons", { query: { country: open, living: "true", limit: 200 } }).then((r) => setPeople(r.items));
  }, [open]);

  if (!data) return <ActivityIndicator style={{ marginTop: 40 }} />;
  const max = data.countries[0]?.count ?? 1;

  return (
    <ScrollView style={{ backgroundColor: colors.cotton }} contentContainerStyle={{ paddingBottom: 40 }}>
      <Text style={[s.lead, { padding: 20 }]}>
        {data.living - data.unknown} personnes vivantes dans {data.countries.length} pays.
        {data.unknown ? ` Pays inconnu pour ${data.unknown} autres.` : ""}
      </Text>
      {data.countries.map((c) => (
        <View key={c.country}>
          <Pressable
            onPress={() => setOpen(open === c.country ? null : c.country)}
            style={({ pressed }) => [
              { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 20, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.line },
              (pressed || open === c.country) && { backgroundColor: colors.indigo50 },
            ]}
          >
            <Text style={{ fontFamily: fonts.uiMedium, fontSize: 15, color: colors.indigo900, width: 120 }} numberOfLines={1}>
              {c.country}
            </Text>
            <View style={{ flex: 1 }}>
              <View style={{ height: 8, borderRadius: 2, backgroundColor: colors.brass, width: `${Math.max(3, (c.count / max) * 100)}%` }} />
            </View>
            <Text style={{ fontFamily: fonts.ui, color: colors.muted, width: 36, textAlign: "right" }}>{c.count}</Text>
          </Pressable>
          {open === c.country && people.map((p) => <PersonRow key={p.id} person={p} onPress={() => onOpenPerson(p.id)} />)}
        </View>
      ))}
    </ScrollView>
  );
}
