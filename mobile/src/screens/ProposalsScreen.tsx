// Propositions sur mobile : un chef de branche valide ou refuse depuis son téléphone ;
// un membre suit l'état de ses propositions.

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { api } from "../api";
import { Button, s } from "../components/ui";
import { colors, fonts } from "../theme";

type Proposal = {
  id: string;
  summary: string;
  message: string | null;
  status: "pending" | "accepted" | "rejected" | "withdrawn";
  author_name: string | null;
  review_note: string | null;
  created_at: string;
  can_review: boolean;
};

const STATUS: Record<Proposal["status"], string> = {
  pending: "En attente",
  accepted: "Acceptée",
  rejected: "Refusée",
  withdrawn: "Retirée",
};

export function ProposalsScreen() {
  const [view, setView] = useState<"review" | "mine">("review");
  const [items, setItems] = useState<Proposal[] | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const load = useCallback(() => {
    setItems(null);
    const query = view === "review" ? { view, status: "pending" } : { view, status: "any" };
    void api<Proposal[]>("/proposals", { query }).then(setItems);
  }, [view]);
  useEffect(load, [load]);

  const act = async (id: string, action: "accept" | "reject", body: object = {}) => {
    try {
      await api(`/proposals/${id}/${action}`, { method: "POST", body });
      setRejecting(null);
      setNote("");
      load();
    } catch (e) {
      Alert.alert("Action impossible", (e as Error).message);
    }
  };

  return (
    <ScrollView style={{ backgroundColor: colors.cotton }} contentContainerStyle={{ paddingBottom: 40 }}>
      <View style={{ flexDirection: "row", margin: 16, backgroundColor: colors.indigo50, borderRadius: 8, padding: 3 }}>
        {(
          [
            ["review", "À valider"],
            ["mine", "Mes propositions"],
          ] as const
        ).map(([v, label]) => (
          <Pressable
            key={v}
            onPress={() => setView(v)}
            style={{ flex: 1, alignItems: "center", paddingVertical: 8, borderRadius: 6, backgroundColor: view === v ? colors.white : "transparent" }}
          >
            <Text style={{ fontFamily: view === v ? fonts.uiSemi : fonts.ui, color: colors.indigo900 }}>{label}</Text>
          </Pressable>
        ))}
      </View>
      {!items && <ActivityIndicator style={{ marginTop: 24 }} />}
      {items?.length === 0 && (
        <Text style={[s.lead, { paddingHorizontal: 20 }]}>
          {view === "review" ? "Aucune proposition à valider." : "Vous n'avez envoyé aucune proposition."}
        </Text>
      )}
      {items?.map((p) => (
        <View key={p.id} style={[s.row, { flexDirection: "column", alignItems: "stretch", gap: 6 }]}>
          <Text style={[s.name, { fontSize: 16 }]}>{p.summary}</Text>
          <Text style={s.sub}>
            {view === "review" ? `Par ${p.author_name ?? "un membre"}, ` : `${STATUS[p.status]}, `}
            {new Date(p.created_at).toLocaleDateString("fr-FR")}
          </Text>
          {p.message && <Text style={[s.lead, { color: colors.indigo900 }]}>« {p.message} »</Text>}
          {p.review_note && <Text style={s.sub}>Motif : {p.review_note}</Text>}
          {p.can_review && rejecting !== p.id && (
            <View style={{ flexDirection: "row", gap: 8, marginTop: 6 }}>
              <View style={{ flex: 1 }}>
                <Button title="Accepter" onPress={() => act(p.id, "accept")} />
              </View>
              <View style={{ flex: 1 }}>
                <Button title="Refuser" kind="ghost" onPress={() => setRejecting(p.id)} />
              </View>
            </View>
          )}
          {rejecting === p.id && (
            <View style={{ gap: 8, marginTop: 6 }}>
              <TextInput
                value={note}
                onChangeText={setNote}
                placeholder="Motif du refus, visible par l'auteur"
                placeholderTextColor={colors.muted}
                style={s.input}
                multiline
              />
              <Button title="Confirmer le refus" onPress={() => act(p.id, "reject", { note })} disabled={!note.trim()} />
            </View>
          )}
        </View>
      ))}
    </ScrollView>
  );
}
