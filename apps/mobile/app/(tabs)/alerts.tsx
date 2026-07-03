import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { api, Alert } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { PlateTag } from "@/components/PlateTag";

const C = {
  ink: "#0B0F14",
  surface: "#151B23",
  bone: "#F1F5F9",
  steel: "#64748B",
  signal: "#3B82F6",
  alert: "#EF4444",
  hairline: "#1E293B",
};

const STATUS_TABS = ["new", "ack", "snoozed", "resolved"] as const;

export default function AlertsScreen() {
  const token = useAuthStore((s) => s.token)!;
  const [tab, setTab] = useState<string>("new");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    try {
      const data = await api.alerts.list(token, { status: tab, limit: 50 });
      setAlerts(data.items);
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

  async function ack(id: string) {
    await api.alerts.ack(token, id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  async function resolve(id: string) {
    await api.alerts.resolve(token, id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  return (
    <View style={styles.root}>
      <View style={styles.tabs}>
        {STATUS_TABS.map((t) => (
          <Pressable
            key={t}
            style={[styles.tabBtn, tab === t && styles.tabBtnActive]}
            onPress={() => setTab(t)}
          >
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t}
            </Text>
          </Pressable>
        ))}
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={C.signal} />
        </View>
      ) : (
        <FlatList
          data={alerts}
          keyExtractor={(a) => a.id}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.signal} />}
          ListEmptyComponent={<Text style={styles.empty}>No {tab} alerts</Text>}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                {item.plate_text ? (
                  <PlateTag plate={item.plate_text} size="sm" />
                ) : (
                  <Text style={{ color: C.steel }}>No plate</Text>
                )}
                <Text style={styles.time}>{new Date(item.created_at).toLocaleString()}</Text>
              </View>
              {item.watchlist_name && (
                <Text style={styles.watchlist}>{item.watchlist_name}</Text>
              )}
              {(tab === "new" || tab === "ack") && (
                <View style={styles.actions}>
                  {tab === "new" && (
                    <Pressable style={[styles.action, styles.actionAck]} onPress={() => ack(item.id)}>
                      <Text style={styles.actionText}>Acknowledge</Text>
                    </Pressable>
                  )}
                  <Pressable style={[styles.action, styles.actionResolve]} onPress={() => resolve(item.id)}>
                    <Text style={styles.actionText}>Resolve</Text>
                  </Pressable>
                </View>
              )}
            </View>
          )}
        />
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
  tabText: { color: C.steel, fontSize: 12, textTransform: "uppercase", fontWeight: "600" },
  tabTextActive: { color: C.signal },
  list: { padding: 16, paddingBottom: 40 },
  empty: { color: C.steel, textAlign: "center", marginTop: 40 },
  card: {
    backgroundColor: C.surface,
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: C.hairline,
  },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 },
  time: { color: C.steel, fontSize: 11 },
  watchlist: { color: C.bone, fontSize: 13, fontWeight: "600", marginBottom: 10 },
  actions: { flexDirection: "row", gap: 8 },
  action: { flex: 1, borderRadius: 6, padding: 8, alignItems: "center" },
  actionAck: { backgroundColor: "#F59E0B" },
  actionResolve: { backgroundColor: "#22C55E" },
  actionText: { color: "#fff", fontSize: 12, fontWeight: "700" },
});
