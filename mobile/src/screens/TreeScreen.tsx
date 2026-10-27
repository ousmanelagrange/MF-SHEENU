// Arbre graphique sur mobile : descendance ou ascendance, profondeur réglable,
// défilement dans les deux sens et zoom par boutons. Toucher une personne ouvre sa fiche.

import { type ComponentRef, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View, useWindowDimensions } from "react-native";
import Svg, { Circle, G, Line, Path, Rect, Text as SvgText } from "react-native-svg";
import { api } from "../api";
import { lifeSpan, s } from "../components/ui";
import { colors, fonts } from "../theme";
import { CARD_H, CARD_W, buildIndex, buildTree, cardHeight, layout, type Mode } from "../treeLayout";
import type { Tree } from "../types";

const PAD = 40;

function clip(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export function TreeScreen({ onOpen }: { onOpen: (id: string) => void }) {
  const [data, setData] = useState<Tree | null>(null);
  const [mode, setMode] = useState<Mode>("descendants");
  const [depth, setDepth] = useState(2);
  const [zoom, setZoom] = useState(0.8);
  const scroller = useRef<ComponentRef<typeof ScrollView>>(null);
  const { width: screenWidth } = useWindowDimensions();

  useEffect(() => {
    void api<Tree>("/tree").then(setData);
  }, []);

  const idx = useMemo(() => (data ? buildIndex(data) : null), [data]);
  const focusId = data
    ? mode === "descendants"
      ? (data.root_person_id ?? data.me_person_id ?? data.persons[0]?.id)
      : (data.me_person_id ?? data.persons[0]?.id)
    : undefined;
  const laid = useMemo(() => {
    if (!idx || !focusId) return null;
    const root = buildTree(idx, focusId, mode, depth, new Set());
    return root ? layout(root, mode) : null;
  }, [idx, focusId, mode, depth]);

  // L'arbre est souvent plus large que l'écran : on centre la vue sur la personne de départ.
  useEffect(() => {
    if (!laid) return;
    const focus = laid.nodes.find((n) => n.data.id === focusId) ?? laid.nodes[0];
    const x = (focus.x - laid.bounds.x0 + PAD) * zoom - screenWidth / 2;
    const timer = setTimeout(() => scroller.current?.scrollTo({ x: Math.max(0, x), animated: false }), 50);
    return () => clearTimeout(timer);
  }, [laid, zoom, focusId, screenWidth]);

  if (!data || !laid) return <ActivityIndicator style={{ marginTop: 40 }} />;

  const { x0, y0, x1, y1 } = laid.bounds;
  const width = (x1 - x0 + PAD * 2) * zoom;
  const height = (y1 - y0 + PAD * 2) * zoom;
  const elbow = (sx: number, sy: number, tx: number, ty: number) => {
    const my = (sy + ty) / 2;
    return `M${sx},${sy}V${my}H${tx}V${ty}`;
  };

  return (
    <View style={{ flex: 1, backgroundColor: "#F6F7FA" }}>
      <View style={{ flexDirection: "row", gap: 8, padding: 12, alignItems: "center", flexWrap: "wrap" }}>
        <Toggle
          value={mode}
          options={[
            ["descendants", "Descendance"],
            ["ancestors", "Ascendance"],
          ]}
          onChange={(m) => setMode(m as Mode)}
        />
        <Stepper label={`${depth} gén.`} onMinus={() => setDepth(Math.max(1, depth - 1))} onPlus={() => setDepth(Math.min(8, depth + 1))} />
        <Stepper label={`${Math.round(zoom * 100)} %`} onMinus={() => setZoom(Math.max(0.4, zoom - 0.15))} onPlus={() => setZoom(Math.min(1.6, zoom + 0.15))} />
      </View>
      <ScrollView ref={scroller} horizontal contentContainerStyle={{ minWidth: "100%" }}>
        <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
          <Svg width={width} height={height}>
            <G scale={zoom} translate={`${(PAD - x0) * zoom}, ${(PAD - y0) * zoom}`}>
              {laid.links.map(({ source, target }) => (
                <Path
                  key={`${source.data.id}-${target.data.id}`}
                  d={
                    mode === "descendants"
                      ? elbow(source.x, source.y + cardHeight(source.data, mode), target.x, target.y)
                      : elbow(source.x, source.y, target.x, target.y + CARD_H)
                  }
                  stroke="#A9B1CB"
                  strokeWidth={1.3}
                  fill="none"
                />
              ))}
              {laid.nodes.map((n) => {
                const p = n.data.person;
                const x = n.x - CARD_W / 2;
                const y = n.y;
                const h = cardHeight(n.data, mode);
                const title = p.titles.find((t) => t.active);
                const female = p.sex === "F";
                return (
                  <G key={p.id} onPress={() => onOpen(p.id)}>
                    <Rect x={x} y={y} width={CARD_W} height={h} rx={8} fill={p.id === data.me_person_id ? colors.indigo50 : "#fff"} stroke={p.id === focusId ? colors.indigo700 : colors.line} strokeWidth={p.id === focusId ? 2 : 1} />
                    {title && <Rect x={x} y={y + 10} width={3} height={CARD_H - 20} rx={1.5} fill={title.badge_color} />}
                    <Circle cx={x + 32} cy={y + CARD_H / 2} r={19} fill={female ? "#EFE7EE" : colors.indigo100} />
                    <SvgText x={x + 32} y={y + CARD_H / 2 + 4.5} fontSize={13} textAnchor="middle" fill={female ? "#6A3B5E" : colors.indigo700} fontFamily={fonts.name}>
                      {`${p.first_name?.[0] ?? ""}${p.last_name?.[0] ?? ""}`.toUpperCase()}
                    </SvgText>
                    <SvgText x={x + 60} y={y + 27} fontSize={13.5} fill={colors.indigo900} fontFamily={fonts.name}>
                      {clip(p.display_name, 19)}
                    </SvgText>
                    <SvgText x={x + 60} y={y + 45} fontSize={11.5} fill={colors.muted} fontFamily={fonts.ui}>
                      {clip([lifeSpan(p), p.generation ? `gén. ${p.generation}` : ""].filter(Boolean).join(", "), 30)}
                    </SvgText>
                    {title && (
                      <SvgText x={x + 60} y={y + 58} fontSize={10.5} fill={title.badge_color} fontFamily={fonts.uiSemi}>
                        {title.name}
                      </SvgText>
                    )}
                    {mode === "descendants" &&
                      n.data.spouses.slice(0, 3).map((sp, i) => (
                        <G key={sp.id}>
                          <Line x1={x + 12} x2={x + CARD_W - 12} y1={y + CARD_H + i * 22} y2={y + CARD_H + i * 22} stroke="#EEF0F5" />
                          <SvgText x={x + 14} y={y + CARD_H + i * 22 + 15} fontSize={11.5} fill={colors.indigo900} fontFamily={fonts.ui}>
                            {`∞ ${clip(sp.display_name, 24)}`}
                          </SvgText>
                        </G>
                      ))}
                    {n.data.hiddenCount > 0 && (
                      <SvgText x={n.x} y={mode === "descendants" ? y + h + 18 : y - 8} fontSize={11} textAnchor="middle" fill={colors.indigo700} fontFamily={fonts.uiSemi}>
                        {`+${n.data.hiddenCount}`}
                      </SvgText>
                    )}
                  </G>
                );
              })}
            </G>
          </Svg>
        </ScrollView>
      </ScrollView>
    </View>
  );
}

function Toggle({ value, options, onChange }: { value: string; options: [string, string][]; onChange: (v: string) => void }) {
  return (
    <View style={{ flexDirection: "row", backgroundColor: colors.indigo50, borderRadius: 8, padding: 3 }}>
      {options.map(([v, label]) => (
        <Pressable
          key={v}
          onPress={() => onChange(v)}
          style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 6, backgroundColor: value === v ? colors.white : "transparent" }}
        >
          <Text style={{ fontFamily: value === v ? fonts.uiSemi : fonts.ui, color: colors.indigo900, fontSize: 14 }}>{label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

function Stepper({ label, onMinus, onPlus }: { label: string; onMinus: () => void; onPlus: () => void }) {
  const btn = { paddingHorizontal: 12, paddingVertical: 6 };
  return (
    <View style={{ flexDirection: "row", alignItems: "center", borderWidth: 1, borderColor: colors.line, borderRadius: 8, backgroundColor: colors.white }}>
      <Pressable onPress={onMinus} style={btn} accessibilityLabel="Moins">
        <Text style={s.meta}>−</Text>
      </Pressable>
      <Text style={[s.meta, { color: colors.indigo900, minWidth: 48, textAlign: "center" }]}>{label}</Text>
      <Pressable onPress={onPlus} style={btn} accessibilityLabel="Plus">
        <Text style={s.meta}>+</Text>
      </Pressable>
    </View>
  );
}
