// Briques d'interface mobiles : marque ntienya, portrait, badge de titre, ligne de personne, champ, bouton.

import { Image, Pressable, StyleSheet, Text, TextInput, View, type TextInputProps } from "react-native";
import Svg, { Path, Rect } from "react-native-svg";
import { colors, fonts } from "../theme";
import type { PersonSummary } from "../types";

export function Mark({ size = 32, inverted = false }: { size?: number; inverted?: boolean }) {
  const ground = inverted ? "#F4F5F8" : colors.indigo700;
  const ink = inverted ? colors.indigo700 : "#F4F5F8";
  return (
    <Svg width={size} height={size} viewBox="0 0 48 48">
      <Rect width={48} height={48} rx={9} fill={ground} />
      {["M24 7l7 7-7 7-7-7z", "M15 18l7 7-7 7-7-7z", "M33 18l7 7-7 7-7-7z", "M24 27l7 7-7 7-7-7z"].map((d) => (
        <Path key={d} d={d} fill="none" stroke={ink} strokeWidth={2} strokeLinejoin="round" />
      ))}
      {["M24 12l2 2-2 2-2-2z", "M15 23l2 2-2 2-2-2z", "M33 23l2 2-2 2-2-2z", "M24 32l2 2-2 2-2-2z"].map((d) => (
        <Path key={d} d={d} fill={ink} />
      ))}
    </Svg>
  );
}

export function lifeSpan(p: Pick<PersonSummary, "birth_year" | "death_year" | "is_living">) {
  if (!p.birth_year && !p.death_year) return p.is_living ? "" : "Défunt(e)";
  if (p.is_living) return p.birth_year ? `né(e) en ${p.birth_year}` : "";
  return `${p.birth_year ?? "?"} – ${p.death_year ?? "?"}`;
}

export function Avatar({ person, size = 40 }: { person: PersonSummary; size?: number }) {
  const female = person.sex === "F";
  const style = {
    width: size,
    height: size,
    borderRadius: size / 2,
    backgroundColor: female ? "#EFE7EE" : colors.indigo100,
    alignItems: "center" as const,
    justifyContent: "center" as const,
    overflow: "hidden" as const,
    opacity: person.is_living ? 1 : 0.85,
  };
  return (
    <View style={style}>
      {person.photo_url ? (
        <Image source={{ uri: person.photo_url }} style={{ width: size, height: size }} />
      ) : (
        <Text style={{ fontFamily: fonts.name, fontSize: size * 0.38, color: female ? "#6A3B5E" : colors.indigo700 }}>
          {`${person.first_name?.[0] ?? ""}${person.last_name?.[0] ?? ""}`.toUpperCase()}
        </Text>
      )}
    </View>
  );
}

export function TitleChip({ person }: { person: PersonSummary }) {
  const t = person.titles.find((x) => x.active);
  if (!t) return null;
  return (
    <View style={[s.chip, { backgroundColor: `${t.badge_color}1A` }]}>
      <View style={[s.diamond, { backgroundColor: t.badge_color }]} />
      <Text style={[s.chipText, { color: t.badge_color }]}>{t.name}</Text>
    </View>
  );
}

export function PersonRow({
  person,
  meta,
  metaColor,
  onPress,
}: {
  person: PersonSummary;
  meta?: string;
  metaColor?: string;
  onPress?: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [s.row, pressed && { backgroundColor: colors.indigo50 }]}>
      <Avatar person={person} />
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <Text style={s.name} numberOfLines={1}>
            {person.display_name}
          </Text>
          <TitleChip person={person} />
        </View>
        {!!lifeSpan(person) && <Text style={s.sub}>{lifeSpan(person)}</Text>}
      </View>
      {meta ? <Text style={[s.meta, metaColor ? { color: metaColor, fontFamily: fonts.uiMedium } : null]}>{meta}</Text> : null}
    </Pressable>
  );
}

export function Field(props: TextInputProps & { label: string }) {
  return (
    <View style={{ marginBottom: 16 }}>
      <Text style={s.label}>{props.label}</Text>
      <TextInput placeholderTextColor={colors.muted} {...props} style={[s.input, props.style]} />
    </View>
  );
}

export function Button({ title, onPress, disabled, kind = "primary" }: { title: string; onPress: () => void; disabled?: boolean; kind?: "primary" | "ghost" }) {
  const primary = kind === "primary";
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        s.btn,
        primary ? { backgroundColor: colors.indigo700 } : { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.white },
        (pressed || disabled) && { opacity: 0.75 },
      ]}
    >
      <Text style={[s.btnText, { color: primary ? colors.white : colors.indigo900 }]}>{title}</Text>
    </Pressable>
  );
}

export const s = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.line,
    backgroundColor: colors.white,
  },
  name: { fontFamily: fonts.name, fontSize: 16, color: colors.indigo900, flexShrink: 1 },
  sub: { fontFamily: fonts.ui, fontSize: 13.5, color: colors.muted, marginTop: 2 },
  meta: { fontFamily: fonts.ui, fontSize: 13, color: colors.muted },
  chip: { flexDirection: "row", alignItems: "center", gap: 5, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 4 },
  diamond: { width: 6, height: 6, transform: [{ rotate: "45deg" }] },
  chipText: { fontFamily: fonts.uiMedium, fontSize: 12 },
  label: { fontFamily: fonts.uiMedium, fontSize: 14, color: colors.indigo900, marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 11,
    fontFamily: fonts.ui,
    fontSize: 16,
    color: colors.indigo900,
    backgroundColor: colors.white,
  },
  btn: { borderRadius: 6, paddingVertical: 13, alignItems: "center" },
  btnText: { fontFamily: fonts.uiSemi, fontSize: 16 },
  h1: { fontFamily: fonts.name, fontSize: 28, color: colors.indigo900 },
  lead: { fontFamily: fonts.ui, fontSize: 15, color: colors.muted, lineHeight: 22 },
  section: { fontFamily: fonts.uiSemi, fontSize: 14, color: colors.muted, paddingHorizontal: 20, paddingTop: 24, paddingBottom: 8 },
  error: { fontFamily: fonts.ui, color: colors.camwood, marginBottom: 12 },
});

/** Choix entre quelques vues (ex. « À valider » / « Mes propositions »). */
export function Segmented<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <View style={{ flexDirection: "row", margin: 16, backgroundColor: colors.indigo50, borderRadius: 8, padding: 3 }}>
      {options.map(([v, label]) => (
        <Pressable
          key={v}
          accessibilityRole="tab"
          accessibilityState={{ selected: value === v }}
          onPress={() => onChange(v)}
          style={{ flex: 1, alignItems: "center", paddingVertical: 8, borderRadius: 6, backgroundColor: value === v ? colors.white : "transparent" }}
        >
          <Text style={{ fontFamily: value === v ? fonts.uiSemi : fonts.ui, color: colors.indigo900 }}>{label}</Text>
        </Pressable>
      ))}
    </View>
  );
}
