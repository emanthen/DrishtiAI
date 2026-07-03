import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { api, VisitorPass, VisitorPassCreate } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { PlateTag } from "@/components/PlateTag";

const C = {
  ink: "#0B0F14",
  surface: "#151B23",
  bone: "#F1F5F9",
  steel: "#64748B",
  signal: "#3B82F6",
  confirm: "#22C55E",
  alert: "#EF4444",
  hairline: "#1E293B",
};

const STATUS_TABS = ["active", "upcoming", "expired", "used"] as const;

function toLocalInput(d: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function PassesScreen() {
  const token = useAuthStore((s) => s.token)!;
  const [tab, setTab] = useState<string>("active");
  const [passes, setPasses] = useState<VisitorPass[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const now = new Date();
  const plus24 = new Date(now.getTime() + 24 * 60 * 60 * 1000);
  const [plate, setPlate] = useState("");
  const [validFrom, setValidFrom] = useState(toLocalInput(now));
  const [validTo, setValidTo] = useState(toLocalInput(plus24));
  const [singleUse, setSingleUse] = useState(false);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api.visitorPasses.mine(token, tab);
      setPasses(data);
    } catch {}
  }

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
  }, [tab]);

  async function onRefresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  async function handleCreate() {
    if (!plate.trim()) { setFormError("Plate is required"); return; }
    setFormError(null);
    setSaving(true);
    try {
      const body: VisitorPassCreate = {
        plate: plate.trim().toUpperCase(),
        valid_from: new Date(validFrom).toISOString(),
        valid_to: new Date(validTo).toISOString(),
        single_use: singleUse,
        notes: notes.trim() || undefined,
      };
      await api.visitorPasses.create(token, body);
      setPlate(""); setNotes(""); setSingleUse(false);
      setShowForm(false);
      if (tab === "active" || tab === "upcoming") load();
    } catch (e: any) {
      setFormError(e.message ?? "Failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleCancel(id: string) {
    await api.visitorPasses.cancel(token, id);
    setPasses((prev) => prev.filter((p) => p.id !== id));
  }

  function passStatusColor(s: string) {
    if (s === "active") return C.confirm;
    if (s === "upcoming") return C.signal;
    if (s === "expired" || s === "used") return C.steel;
    return C.steel;
  }

  return (
    <View style={styles.root}>
      <View style={styles.tabs}>
        {STATUS_TABS.map((t) => (
          <Pressable key={t} style={[styles.tabBtn, tab === t && styles.tabBtnActive]} onPress={() => setTab(t)}>
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>{t}</Text>
          </Pressable>
        ))}
      </View>

      <Pressable style={styles.addBtn} onPress={() => setShowForm((v) => !v)}>
        <Text style={styles.addBtnText}>{showForm ? "Cancel" : "+ New Pass"}</Text>
      </Pressable>

      {showForm && (
        <ScrollView style={styles.form} keyboardShouldPersistTaps="handled">
          {formError && <Text style={styles.error}>{formError}</Text>}
          <Text style={styles.label}>Plate Number</Text>
          <TextInput
            style={styles.input}
            value={plate}
            onChangeText={setPlate}
            autoCapitalize="characters"
            placeholder="BA 1 PA 0001"
            placeholderTextColor={C.steel}
          />
          <Text style={styles.label}>Valid From</Text>
          <TextInput
            style={styles.input}
            value={validFrom}
            onChangeText={setValidFrom}
            placeholder="YYYY-MM-DDTHH:MM"
            placeholderTextColor={C.steel}
            keyboardType="numbers-and-punctuation"
          />
          <Text style={styles.label}>Valid To</Text>
          <TextInput
            style={styles.input}
            value={validTo}
            onChangeText={setValidTo}
            placeholder="YYYY-MM-DDTHH:MM"
            placeholderTextColor={C.steel}
            keyboardType="numbers-and-punctuation"
          />
          <View style={styles.switchRow}>
            <Text style={styles.label}>Single use</Text>
            <Switch value={singleUse} onValueChange={setSingleUse} trackColor={{ true: C.signal }} />
          </View>
          <Text style={styles.label}>Notes (optional)</Text>
          <TextInput
            style={[styles.input, { height: 70 }]}
            value={notes}
            onChangeText={setNotes}
            multiline
            placeholder="Guest name, purpose…"
            placeholderTextColor={C.steel}
          />
          <Pressable style={[styles.saveBtn, saving && { opacity: 0.5 }]} onPress={handleCreate} disabled={saving}>
            <Text style={styles.saveBtnText}>{saving ? "Saving…" : "Create Pass"}</Text>
          </Pressable>
        </ScrollView>
      )}

      {!showForm && (
        loading ? (
          <View style={styles.center}><ActivityIndicator color={C.signal} /></View>
        ) : (
          <FlatList
            data={passes}
            keyExtractor={(p) => p.id}
            contentContainerStyle={styles.list}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.signal} />}
            ListEmptyComponent={<Text style={styles.empty}>No {tab} passes</Text>}
            renderItem={({ item }) => (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <PlateTag plate={item.plate} size="sm" />
                  <View style={[styles.badge, { backgroundColor: passStatusColor(item.pass_status) }]}>
                    <Text style={styles.badgeText}>{item.pass_status}</Text>
                  </View>
                </View>
                <Text style={styles.dateText}>
                  {new Date(item.valid_from).toLocaleString()} → {new Date(item.valid_to).toLocaleString()}
                </Text>
                {item.single_use && <Text style={styles.singleUseTag}>Single use</Text>}
                {item.notes && <Text style={styles.notesText}>{item.notes}</Text>}
                {(item.pass_status === "active" || item.pass_status === "upcoming") && (
                  <Pressable style={styles.cancelBtn} onPress={() => handleCancel(item.id)}>
                    <Text style={styles.cancelBtnText}>Cancel Pass</Text>
                  </Pressable>
                )}
              </View>
            )}
          />
        )
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.ink },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  tabs: { flexDirection: "row", borderBottomWidth: 1, borderBottomColor: C.hairline },
  tabBtn: { flex: 1, paddingVertical: 12, alignItems: "center" },
  tabBtnActive: { borderBottomWidth: 2, borderBottomColor: C.signal },
  tabText: { color: C.steel, fontSize: 11, textTransform: "uppercase", fontWeight: "600" },
  tabTextActive: { color: C.signal },
  addBtn: { margin: 16, marginBottom: 8, backgroundColor: C.signal, borderRadius: 8, padding: 12, alignItems: "center" },
  addBtnText: { color: "#fff", fontWeight: "700", fontSize: 14 },
  form: { paddingHorizontal: 16, paddingBottom: 20, maxHeight: 480 },
  label: { color: C.steel, fontSize: 11, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 6, marginTop: 12 },
  input: { backgroundColor: C.surface, borderWidth: 1, borderColor: C.hairline, borderRadius: 8, color: C.bone, padding: 12, fontSize: 14 },
  switchRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 12 },
  error: { color: C.alert, fontSize: 13, marginBottom: 8 },
  saveBtn: { backgroundColor: C.confirm, borderRadius: 8, padding: 14, alignItems: "center", marginTop: 16, marginBottom: 20 },
  saveBtnText: { color: "#fff", fontWeight: "700" },
  list: { padding: 16, paddingBottom: 40 },
  empty: { color: C.steel, textAlign: "center", marginTop: 40 },
  card: { backgroundColor: C.surface, borderRadius: 10, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: C.hairline },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  badge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  badgeText: { color: "#fff", fontSize: 10, fontWeight: "700", textTransform: "uppercase" },
  dateText: { color: C.steel, fontSize: 11, marginBottom: 4 },
  singleUseTag: { color: "#F59E0B", fontSize: 11, fontWeight: "600", marginBottom: 4 },
  notesText: { color: C.bone, fontSize: 12, marginBottom: 8 },
  cancelBtn: { marginTop: 6, borderWidth: 1, borderColor: C.alert, borderRadius: 6, padding: 8, alignItems: "center" },
  cancelBtnText: { color: C.alert, fontSize: 12, fontWeight: "700" },
});
