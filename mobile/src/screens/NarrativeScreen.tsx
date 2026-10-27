// Un récit sur mobile : écouter l'enregistrement, lire une couche (langue d'origine,
// français, anglais) et proposer une correction ou une traduction.

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, Text, TextInput, View } from "react-native";
import { api } from "../api";
import { isQueued, send, tellQueued } from "../sync";
import { AudioPlayer } from "../components/AudioPlayer";
import { Button, PersonRow, s, Segmented } from "../components/ui";
import { LAYERS, when, type LayerName, type Narrative } from "../memory";
import { colors, fonts } from "../theme";

export function NarrativeScreen({ id, onOpenPerson }: { id: string; onOpenPerson: (id: string) => void }) {
  const [n, setN] = useState<Narrative | null>(null);
  const [layer, setLayer] = useState<LayerName>("original");
  const [draft, setDraft] = useState<string | null>(null);

  const load = useCallback(() => void api<Narrative>(`/narratives/${id}`).then(setN), [id]);
  useEffect(load, [load]);

  if (!n) return <ActivityIndicator style={{ marginTop: 40 }} />;
  const state = n.texts[layer];

  const propose = async () => {
    try {
      const r = await send(`/narratives/${n.id}/texts`, {
        method: "POST",
        body: { layer, text: draft },
        label: `Texte du récit « ${n.title} »`,
      });
      setDraft(null);
      if (isQueued(r)) return tellQueued();
      Alert.alert(n.can_review ? "Texte validé" : "Proposition envoyée", n.can_review ? "" : "Un gardien de la mémoire la relira.");
      load();
    } catch (e) {
      Alert.alert("Envoi impossible", (e as Error).message);
    }
  };

  return (
    <ScrollView
      style={{ backgroundColor: colors.cotton }}
      contentContainerStyle={{ paddingBottom: 48 }}
      keyboardShouldPersistTaps="handled"
    >
      <View style={{ padding: 20, gap: 8 }}>
        <Text style={[s.h1, { fontSize: 26, lineHeight: 33 }]}>{n.title}</Text>
        {n.teller && <Text style={s.sub}>Raconté par {n.teller.display_name}</Text>}
        <Text style={s.sub}>{[n.language, when(n), n.place].filter(Boolean).join(", ")}</Text>
        {n.media_url && n.media_kind === "audio" && (
          <View style={{ marginTop: 10 }}>
            <AudioPlayer uri={n.media_url} />
          </View>
        )}
      </View>

      <Segmented
        value={layer}
        onChange={(v) => (setLayer(v), setDraft(null))}
        options={LAYERS.map((l) => [l.key, l.label] as [LayerName, string])}
      />

      <View style={{ paddingHorizontal: 20 }}>
        {draft !== null ? (
          <>
            <TextInput
              value={draft}
              onChangeText={setDraft}
              multiline
              autoFocus
              style={[s.input, { minHeight: 220, textAlignVertical: "top", fontFamily: fonts.nameRegular, lineHeight: 24 }]}
            />
            <View style={{ flexDirection: "row", gap: 10, marginTop: 12 }}>
              <View style={{ flex: 1 }}>
                <Button title="Annuler" kind="ghost" onPress={() => setDraft(null)} />
              </View>
              <View style={{ flex: 1 }}>
                <Button title={n.can_review ? "Valider" : "Proposer"} onPress={propose} disabled={!draft.trim()} />
              </View>
            </View>
          </>
        ) : (
          <>
            {state.validated ? (
              <Text style={{ fontFamily: fonts.nameRegular, fontSize: 17, lineHeight: 28, color: colors.indigo900 }}>
                {state.validated.text}
              </Text>
            ) : (
              <Text style={[s.lead, { fontStyle: "italic" }]}>
                {layer === "original" ? "Pas encore de transcription." : "Pas encore de traduction."}
              </Text>
            )}
            {state.pending > 0 && (
              <Text style={[s.sub, { color: colors.brass, fontFamily: fonts.uiSemi, marginTop: 10 }]}>
                {state.pending} proposition{state.pending > 1 ? "s" : ""} en relecture
              </Text>
            )}
            <View style={{ marginTop: 16 }}>
              <Button
                kind="ghost"
                title={state.validated ? "Proposer une correction" : layer === "original" ? "Transcrire" : "Traduire"}
                onPress={() => setDraft(state.validated?.text ?? "")}
              />
            </View>
          </>
        )}
      </View>

      {n.persons.length > 0 && (
        <>
          <Text style={s.section}>Personnes dont parle le récit</Text>
          {n.persons.map((p) => (
            <PersonRow key={p.id} person={p} onPress={() => onOpenPerson(p.id)} />
          ))}
        </>
      )}
    </ScrollView>
  );
}
