import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { api, Alert, AnalyticsOverview } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { StatCard } from "@/components/StatCard";
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

export default function HomeScreen() {
  const token = useAuthStore((s) => s.token)!;
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    try {
      const [ov, al] = await Promise.all([
        api.analytics.overview(token),
        api.alerts.list(token, { limit: 5 }),
      ]);
      setOverview(ov);
      setRecentAlerts(al.items);
    } catch {}
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, []);

  async function onRefresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={C.signal} />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.signal} />}
    >
      <Text style={styles.section}>Overview</Text>
      <View style={styles.cardRow}>
        <StatCard
          label="Open alerts"
          value={overview?.open_alerts ?? "—"}
          accent={(overview?.open_alerts ?? 0) > 0 ? "alert" : "default"}
        />
        <StatCard label="Events today" value={overview?.events_today ?? "—"} />
      </View>
      <View style={[styles.cardRow, { marginTop: 10 }]}>
        <StatCard label="Active parking" value={overview?.active_sessions ?? "—"} />
        <StatCard
          label="Revenue today"
          value={overview ? `NPR ${overview.revenue_today}` : "—"}
          accent="confirm"
        />
      </View>

      <Text style={[styles.section, { marginTop: 28 }]}>Recent Alerts</Text>
      {recentAlerts.length === 0 ? (
        <Text style={styles.empty}>No alerts</Text>
      ) : (
        recentAlerts.map((a) => (
          <View key={a.id} style={styles.alertRow}>
            {a.plate_text ? (
              <PlateTag plate={a.plate_text} size="sm" />
            ) : (
              <Text style={styles.noPlate}>—</Text>
            )}
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={styles.alertName}>{a.watchlist_name ?? "Alert"}</Text>
              <Text style={styles.alertTime}>{new Date(a.created_at).toLocaleString()}</Text>
            </View>
            <View style={[styles.badge, { backgroundColor: statusColor(a.status) }]}>
              <Text style={styles.badgeText}>{a.status}</Text>
            </View>
          </View>
        ))
      )}
    </ScrollView>
  );
}

function statusColor(s: string) {
  if (s === "new") return C.alert;
  if (s === "ack") return "#F59E0B";
  if (s === "resolved") return "#22C55E";
  return C.steel;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.ink },
  content: { padding: 20, paddingBottom: 40 },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: C.ink },
  section: { color: C.steel, fontSize: 11, fontWeight: "700", textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 },
  cardRow: { flexDirection: "row", gap: 10 },
  alertRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: C.surface,
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: C.hairline,
  },
  noPlate: { color: C.steel, fontFamily: "monospace" },
  alertName: { color: C.bone, fontSize: 14, fontWeight: "600" },
  alertTime: { color: C.steel, fontSize: 11, marginTop: 2 },
  badge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  badgeText: { color: "#fff", fontSize: 10, fontWeight: "700", textTransform: "uppercase" },
  empty: { color: C.steel, textAlign: "center", marginTop: 20 },
});
