// Liste des personnes par préséance, avec recherche et chargement progressif.

import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, FlatList, TextInput, View } from "react-native";
import { api, ApiError } from "../api";
import { searchOffline } from "../offline";
import { PersonRow, s } from "../components/ui";
import { colors } from "../theme";
import type { PersonSummary } from "../types";

const PAGE = 40;

export function PeopleScreen({ onOpen }: { onOpen: (id: string) => void }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<PersonSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const load = useCallback(async (query: string, skip: number) => {
    setLoading(true);
    try {
      let r: { items: PersonSummary[]; total: number };
      try {
        r = await api<{ items: PersonSummary[]; total: number }>("/persons", {
          query: { q: query, skip, limit: PAGE, sort: "precedence" },
        });
      } catch (e) {
        // Hors connexion, une recherche jamais faite est menée dans l'arbre gardé sur le téléphone
        const local = e instanceof ApiError && e.code === "offline" ? await searchOffline(query, skip, PAGE) : null;
        if (!local) throw e;
        r = local;
      }
      setTotal(r.total);
      setItems((prev) => (skip === 0 ? r.items : [...prev, ...r.items]));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => void load(q, 0), 250);
  }, [q, load]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.cotton }}>
      <View style={{ padding: 16, paddingBottom: 8 }}>
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder="Rechercher un nom"
          placeholderTextColor={colors.muted}
          style={s.input}
          clearButtonMode="while-editing"
        />
      </View>
      <FlatList
        data={items}
        keyExtractor={(p) => p.id}
        renderItem={({ item }) => (
          <PersonRow person={item} meta={item.generation ? `G${item.generation}` : undefined} onPress={() => onOpen(item.id)} />
        )}
        onEndReachedThreshold={0.4}
        onEndReached={() => {
          if (!loading && items.length < total) void load(q, items.length);
        }}
        ListFooterComponent={loading ? <ActivityIndicator style={{ margin: 20 }} /> : undefined}
      />
    </View>
  );
}
