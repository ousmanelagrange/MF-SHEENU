// Fiche d'une personne : identité, lien avec moi, histoire, parents, conjoints, enfants, fratrie.

import { useEffect, useState } from "react";
import { ActivityIndicator, Linking, Pressable, ScrollView, Text, View } from "react-native";
import { api, ApiError, session } from "../api";
import { personOffline } from "../offline";
import { Avatar, PersonRow, TitleChip, lifeSpan, s } from "../components/ui";
import { colors, fonts } from "../theme";
import type { Kinship, PersonDetail } from "../types";

export function PersonScreen({ id, meId, onOpen }: { id: string; meId: string | null; onOpen: (id: string) => void }) {
  const [p, setP] = useState<PersonDetail | null>(null);
  const [kin, setKin] = useState<Kinship | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    setP(null);
    setKin(null);
    api<PersonDetail>(`/persons/${id}`)
      .then(setP)
      .catch(async (e) => {
        // Fiche jamais ouverte et pas de réseau : reconstituée depuis l'arbre gardé sur le téléphone
        const local = e instanceof ApiError && e.code === "offline" ? await personOffline(id) : null;
        if (local) setP(local);
        else setMissing(true);
      });
    if (meId && meId !== id && session.family) {
      api<Kinship>("/kinship", { query: { to: id } })
        .then(setKin)
        .catch(() => null);
    }
  }, [id, meId]);

  if (missing) return <Text style={[s.lead, { padding: 24 }]}>Cette fiche n'est pas disponible sans connexion.</Text>;
  if (!p) return <ActivityIndicator style={{ marginTop: 40 }} />;

  return (
    <ScrollView style={{ backgroundColor: colors.cotton }} contentContainerStyle={{ paddingBottom: 48 }}>
      <View
        style={{ alignItems: "center", padding: 24, backgroundColor: colors.white, borderBottomWidth: 1, borderBottomColor: colors.line }}
      >
        <Avatar person={p} size={104} />
        <Text style={[s.h1, { textAlign: "center", marginTop: 14 }]}>{p.display_name}</Text>
        <Text style={[s.lead, { textAlign: "center" }]}>
          {[p.traditional_name, lifeSpan(p), p.generation ? `génération ${p.generation}` : null].filter(Boolean).join(", ")}
        </Text>
        <View style={{ marginTop: 10 }}>
          <TitleChip person={p} />
        </View>
        {kin?.label && (
          <Text style={{ marginTop: 14, fontFamily: fonts.ui, fontSize: 15, color: colors.indigo900 }}>
            Pour vous : <Text style={{ fontFamily: fonts.name }}>{kin.label}</Text>
          </Text>
        )}
        {p.phone && (
          <Pressable onPress={() => Linking.openURL(`tel:${p.phone}`)} style={{ marginTop: 12 }}>
            <Text style={{ fontFamily: fonts.uiMedium, color: colors.indigo500 }}>Appeler {p.phone}</Text>
          </Pressable>
        )}
      </View>

      {p.biography && (
        <>
          <Text style={s.section}>Histoire</Text>
          <Text style={[s.lead, { paddingHorizontal: 20, color: colors.indigo900 }]}>{p.biography}</Text>
        </>
      )}

      {p.parents.length > 0 && <Text style={s.section}>Parents</Text>}
      {p.parents.map((r) => (
        <PersonRow
          key={r.relation_id}
          person={r.person}
          meta={r.person.sex === "F" ? "mère" : "père"}
          onPress={() => onOpen(r.person.id)}
        />
      ))}

      {p.spouses.length > 0 && <Text style={s.section}>{p.spouses.length > 1 ? "Conjoints" : "Conjoint"}</Text>}
      {p.spouses.map((u) => (
        <PersonRow
          key={u.union_id}
          person={u.person}
          meta={u.rank ? (u.rank === 1 ? "1re" : `${u.rank}e`) : undefined}
          onPress={() => onOpen(u.person.id)}
        />
      ))}

      {p.children.length > 0 && <Text style={s.section}>Enfants ({p.children.length})</Text>}
      {p.children.map((r) => (
        <PersonRow key={r.relation_id} person={r.person} onPress={() => onOpen(r.person.id)} />
      ))}

      {p.siblings.length > 0 && <Text style={s.section}>Frères et sœurs ({p.siblings.length})</Text>}
      {p.siblings.map((x) => (
        <PersonRow key={x.id} person={x} onPress={() => onOpen(x.id)} />
      ))}
    </ScrollView>
  );
}
