import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { api, ParkingSession } from "@/lib/api";
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
  amber: "#F59E0B",
  hairline: "#1E293B",
};

function duration(s: number | null): string {
  if (s == null) return "—";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${s % 60}s`;
}

function liveDuration(entryTs: string | null): string {
  if (!entryTs) return "—";
  return duration(Math.floor((Date.now() - new Date(entryTs).getTime()) / 1000));
}

function paymentColor(status: string) {
  if (status === "paid") return C.confirm;
  if (status === "waived") return C.steel;
  return C.amber;
}

export default function ParkingScreen() {
  const token = useAuthStore((s) => s.token)!;
  const [sessions, setSessions] = useState<ParkingSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.parking.listActive(token);
      setSessions(data);
    } catch {}
  }, [token]);

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  async function handleClose(id: string) {
    Alert.alert(
      "Close Session",
      "Manually close this parking session? The exit time will be set to now and the charge calculated.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Close",
          style: "destructive",
          onPress: async () => {
            setActionId(id);
            try {
              await api.parking.close(token, id);
              setSessions((prev) => prev.filter((s) => s.id !== id));
            } catch {
              Alert.alert("Error", "Could not close session — try again.");
            } finally {
              setActionId(null);
            }
          },
        },
      ]
    );
  }

  async function handleMarkPaid(id: string) {
    setActionId(id);
    try {
      const updated = await api.parking.markPaid(token, id);
      setSessions((prev) => prev.map((s) => (s.id === id ? updated : s)));
    } catch {
      Alert.alert("Error", "Could not mark as paid — try again.");
    } finally {
      setActionId(null);
    }
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={C.signal} />
      </View>
    );
  }

  return (
    <FlatList
      style={styles.root}
      data={sessions}
      keyExtractor={(s) => s.id}
      contentContainerStyle={styles.list}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.signal} />
      }
      ListEmptyComponent={
        <View style={styles.emptyWrap}>
          <Text style={styles.emptyTitle}>No active sessions</Text>
          <Text style={styles.emptySub}>All vehicles have exited.</Text>
        </View>
      }
      renderItem={({ item }) => {
        const isBusy = actionId === item.id;
        return (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              {item.plate_text ? (
                <PlateTag plate={item.plate_text} size="sm" />
              ) : (
                <Text style={styles.noPlate}>Unknown plate</Text>
              )}
              <View style={[styles.payBadge, { backgroundColor: paymentColor(item.payment_status) }]}>
                <Text style={styles.payText}>{item.payment_status.toUpperCase()}</Text>
              </View>
            </View>

            <View style={styles.statsRow}>
              <View style={styles.stat}>
                <Text style={styles.statLabel}>Duration</Text>
                <Text style={styles.statValue}>
                  {item.duration_s != null ? duration(item.duration_s) : liveDuration(item.entry_ts)}
                </Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statLabel}>Amount due</Text>
                <Text style={[styles.statValue, { color: item.amount_due ? C.amber : C.steel }]}>
                  {item.amount_due != null ? `NPR ${item.amount_due.toFixed(0)}` : "—"}
                </Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statLabel}>Entry</Text>
                <Text style={styles.statValue}>
                  {item.entry_ts ? new Date(item.entry_ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                </Text>
              </View>
            </View>

            <View style={styles.actions}>
              {!item.exit_ts && (
                <Pressable
                  style={[styles.actionBtn, styles.closeBtn, isBusy && styles.busy]}
                  onPress={() => handleClose(item.id)}
                  disabled={isBusy}
                >
                  <Text style={styles.actionText}>Close Session</Text>
                </Pressable>
              )}
              {item.payment_status === "pending" && (
                <Pressable
                  style={[styles.actionBtn, styles.paidBtn, isBusy && styles.busy]}
                  onPress={() => handleMarkPaid(item.id)}
                  disabled={isBusy}
                >
                  <Text style={styles.actionText}>Mark Paid</Text>
                </Pressable>
              )}
            </View>
          </View>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.ink },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: C.ink },
  list: { padding: 14, paddingBottom: 40 },
  emptyWrap: { alignItems: "center", marginTop: 60 },
  emptyTitle: { color: C.bone, fontSize: 16, fontWeight: "600", marginBottom: 6 },
  emptySub: { color: C.steel, fontSize: 13 },
  card: {
    backgroundColor: C.surface,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: C.hairline,
  },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  noPlate: { color: C.steel, fontFamily: "monospace" },
  payBadge: { borderRadius: 4, paddingHorizontal: 7, paddingVertical: 3 },
  payText: { color: "#fff", fontSize: 10, fontWeight: "700" },
  statsRow: { flexDirection: "row", marginBottom: 12, gap: 8 },
  stat: { flex: 1 },
  statLabel: { color: C.steel, fontSize: 10, textTransform: "uppercase", fontWeight: "600", marginBottom: 2 },
  statValue: { color: C.bone, fontSize: 14, fontWeight: "600" },
  actions: { flexDirection: "row", gap: 8 },
  actionBtn: { flex: 1, borderRadius: 7, padding: 10, alignItems: "center" },
  closeBtn: { backgroundColor: C.alert },
  paidBtn: { backgroundColor: C.confirm },
  busy: { opacity: 0.4 },
  actionText: { color: "#fff", fontWeight: "700", fontSize: 13 },
});
