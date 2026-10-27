// Une collecte sur mobile : avancement, ma part, déclarer un paiement,
// paiements à valider (trésorier) et état de chacun.

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { api } from "../api";
import { Button, Field, PersonRow, s } from "../components/ui";
import { STATUS_COLORS, STATUS_LABELS, money } from "../money";
import { colors, fonts } from "../theme";
import type { ContributionEvent, DueRow, DueStatus, Payment } from "../types";
import { ProgressBar } from "./ContributionsScreen";

const METHODS: [Payment["method"], string][] = [
  ["mobile_money", "Mobile Money"],
  ["cash", "Espèces"],
  ["bank", "Virement"],
];

export function EventScreen({ id, meId, onOpenPerson }: { id: string; meId: string | null; onOpenPerson: (id: string) => void }) {
  const [event, setEvent] = useState<ContributionEvent | null>(null);
  const [rows, setRows] = useState<DueRow[]>([]);
  const [pending, setPending] = useState<Payment[]>([]);
  const [filter, setFilter] = useState<DueStatus | "any">("unpaid");
  const [declaring, setDeclaring] = useState(false);

  const load = useCallback(async () => {
    const e = await api<ContributionEvent>(`/contributions/events/${id}`);
    setEvent(e);
    setRows(await api<DueRow[]>(`/contributions/events/${id}/dues`));
    setPending(e.can_manage ? await api<Payment[]>(`/contributions/events/${id}/payments`, { query: { status: "declared" } }) : []);
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);

  if (!event) return <ActivityIndicator style={{ marginTop: 40 }} />;
  const mine = rows.find((r) => r.person.id === meId);
  const open = event.status === "open";

  const review = async (p: Payment, action: "validate" | "reject") => {
    try {
      await api(`/contributions/payments/${p.id}/${action}`, {
        method: "POST",
        body: action === "reject" ? { note: "Paiement non reçu" } : {},
      });
      void load();
    } catch (e) {
      Alert.alert("Action impossible", (e as Error).message);
    }
  };

  return (
    <ScrollView style={{ backgroundColor: colors.cotton }} contentContainerStyle={{ paddingBottom: 48 }}>
      <View style={{ padding: 20, gap: 14, backgroundColor: colors.white, borderBottomWidth: 1, borderBottomColor: colors.line }}>
        <Text style={s.h1}>{event.title}</Text>
        {event.description && <Text style={s.lead}>{event.description}</Text>}
        <ProgressBar event={event} />
        <Text style={s.sub}>
          {event.totals.paid} à jour, {event.totals.partial} partiels, {event.totals.unpaid} non payés
        </Text>
        {mine && (
          <View style={{ padding: 14, borderRadius: 8, backgroundColor: colors.indigo50, gap: 4 }}>
            <Text style={{ fontFamily: fonts.uiSemi, color: colors.indigo900 }}>Ma part</Text>
            <Text style={{ fontFamily: fonts.ui, color: colors.indigo900 }}>
              {money(mine.paid, event.currency)} payés sur {money(mine.amount, event.currency)}, {STATUS_LABELS[mine.status].toLowerCase()}
            </Text>
          </View>
        )}
        {open && !declaring && <Button title="Déclarer un paiement" onPress={() => setDeclaring(true)} />}
        {declaring && (
          <PaymentForm
            event={event}
            personId={meId}
            defaultAmount={mine ? Math.max(mine.amount - mine.paid, 0) : 0}
            onCancel={() => setDeclaring(false)}
            onDone={() => {
              setDeclaring(false);
              void load();
            }}
          />
        )}
      </View>

      {pending.length > 0 && (
        <>
          <Text style={s.section}>À valider ({pending.length})</Text>
          {pending.map((p) => (
            <View key={p.id} style={[s.row, { flexDirection: "column", alignItems: "stretch", gap: 8 }]}>
              <Text style={s.name}>
                {p.person?.display_name} : {money(p.amount, event.currency)}
              </Text>
              <Text style={s.sub}>
                {p.reference ? `Réf. ${p.reference}, ` : ""}déclaré par {p.declared_by_name}
              </Text>
              <View style={{ flexDirection: "row", gap: 8 }}>
                <View style={{ flex: 1 }}>
                  <Button title="Valider" onPress={() => review(p, "validate")} />
                </View>
                <View style={{ flex: 1 }}>
                  <Button title="Refuser" kind="ghost" onPress={() => review(p, "reject")} />
                </View>
              </View>
            </View>
          ))}
        </>
      )}

      <View style={{ flexDirection: "row", gap: 6, paddingHorizontal: 16, paddingTop: 20, flexWrap: "wrap" }}>
        {(["unpaid", "partial", "paid", "any"] as const).map((f) => (
          <Pressable
            key={f}
            onPress={() => setFilter(f)}
            style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: filter === f ? colors.indigo700 : colors.white, borderWidth: 1, borderColor: filter === f ? colors.indigo700 : colors.line }}
          >
            <Text style={{ fontFamily: fonts.uiMedium, fontSize: 13, color: filter === f ? colors.white : colors.indigo900 }}>
              {f === "any" ? "Tous" : STATUS_LABELS[f]}
            </Text>
          </Pressable>
        ))}
      </View>
      <View style={{ marginTop: 8 }}>
        {rows
          .filter((r) => filter === "any" || r.status === filter)
          .slice(0, 200)
          .map((r) => (
            <PersonRow
              key={r.person.id}
              person={r.person}
              meta={`${money(r.paid, event.currency)} / ${money(r.amount, event.currency)}`}
              metaColor={STATUS_COLORS[r.status]}
              onPress={() => onOpenPerson(r.person.id)}
            />
          ))}
      </View>
    </ScrollView>
  );
}

function PaymentForm({
  event,
  personId,
  defaultAmount,
  onCancel,
  onDone,
}: {
  event: ContributionEvent;
  personId: string | null;
  defaultAmount: number;
  onCancel: () => void;
  onDone: () => void;
}) {
  const [amount, setAmount] = useState(defaultAmount ? String(defaultAmount) : "");
  const [method, setMethod] = useState<Payment["method"]>("mobile_money");
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!personId) return;
    setBusy(true);
    try {
      const p = await api<Payment>(`/contributions/events/${event.id}/payments`, {
        method: "POST",
        body: { person_id: personId, amount: Number(amount), method, reference: reference || null },
      });
      Alert.alert(p.status === "validated" ? "Paiement enregistré" : "Paiement déclaré", p.status === "validated" ? "" : "Le trésorier va le valider.");
      onDone();
    } catch (e) {
      Alert.alert("Déclaration impossible", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={{ gap: 4 }}>
      <Field label="Montant" value={amount} onChangeText={(v) => setAmount(v.replace(/\D/g, ""))} keyboardType="number-pad" />
      <Text style={s.label}>Moyen</Text>
      <View style={{ flexDirection: "row", gap: 6, marginBottom: 16 }}>
        {METHODS.map(([value, label]) => (
          <Pressable
            key={value}
            onPress={() => setMethod(value)}
            style={{ flex: 1, alignItems: "center", paddingVertical: 9, borderRadius: 6, borderWidth: 1, borderColor: method === value ? colors.indigo700 : colors.line, backgroundColor: method === value ? colors.indigo50 : colors.white }}
          >
            <Text style={{ fontFamily: fonts.uiMedium, fontSize: 13, color: colors.indigo900 }}>{label}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={s.label}>Référence de la transaction</Text>
      <TextInput value={reference} onChangeText={setReference} style={[s.input, { marginBottom: 16 }]} placeholder="MP261027…" placeholderTextColor={colors.muted} autoCapitalize="characters" />
      <Button title={busy ? "Envoi…" : "Déclarer"} onPress={submit} disabled={busy || !Number(amount)} />
      <Button title="Annuler" kind="ghost" onPress={onCancel} />
    </View>
  );
}
