import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { api, Event } from "@/lib/api";
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

const KIND_COLOR: Record<string, string> = {
  entry:  C.confirm,
  exit:   C.signal,
  anpr:   C.steel,
  parked: C.amber,
};

const KIND_LABEL: Record<string, string> = {
  entry:  "ENTRY",
  exit:   "EXIT",
  anpr:   "READ",
  parked: "PARKED",
};

function ago(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
}

// Two-hours-ago ISO string for time-bounded queries
function twoHoursAgo() {
  return new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
}

export default function EventsScreen() {
  const token = useAuthStore((s) => s.token)!;
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (reset = false) => {
    try {
      const page = await api.events.list(token, {
        limit: 40,
        from: twoHoursAgo(),
      });
      setEvents(reset || !events.length ? page.items : page.items);
      setNextCursor(page.next_cursor);
    } catch {}
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    load(true).finally(() => setLoading(false));
    // Poll every 10 seconds for live feel
    pollRef.current = setInterval(() => load(true), 10_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    await load(true);
    setRefreshing(false);
  }

  async function loadMore() {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await api.events.list(token, { limit: 40, cursor: nextCursor });
      setEvents((prev) => [...prev, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch {}
    setLoadingMore(false);
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
      data={events}
      keyExtractor={(e) => e.id}
      contentContainerStyle={styles.list}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={C.signal} />
      }
      onEndReached={loadMore}
      onEndReachedThreshold={0.3}
      ListEmptyComponent={
        <Text style={styles.empty}>No events in the last 2 hours</Text>
      }
      ListFooterComponent={
        loadingMore ? <ActivityIndicator color={C.signal} style={{ margin: 16 }} /> : null
      }
      renderItem={({ item }) => (
        <View style={styles.card}>
          <View style={styles.row}>
            {item.plate ? (
              <PlateTag plate={item.plate.text} size="sm" />
            ) : (
              <Text style={styles.noPlate}>No plate</Text>
            )}
            <View style={styles.right}>
              <View style={[styles.kindBadge, { backgroundColor: KIND_COLOR[item.kind] ?? C.steel }]}>
                <Text style={styles.kindText}>{KIND_LABEL[item.kind] ?? item.kind.toUpperCase()}</Text>
              </View>
              <Text style={styles.time}>{ago(item.ts)}</Text>
            </View>
          </View>
          <View style={styles.meta}>
            {item.vehicle?.color && (
              <Text style={styles.metaText}>{item.vehicle.color}</Text>
            )}
            {item.vehicle?.type && (
              <Text style={styles.metaDot}> · </Text>
            )}
            {item.vehicle?.type && (
              <Text style={styles.metaText}>{item.vehicle.type}</Text>
            )}
            {item.confidence != null && (
              <>
                <Text style={styles.metaDot}> · </Text>
                <Text style={[
                  styles.metaText,
                  { color: item.confidence >= 0.8 ? C.confirm : item.confidence >= 0.5 ? C.amber : C.alert },
                ]}>
                  {Math.round(item.confidence * 100)}%
                </Text>
              </>
            )}
          </View>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.ink },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: C.ink },
  list: { padding: 14, paddingBottom: 40 },
  empty: { color: C.steel, textAlign: "center", marginTop: 40 },
  card: {
    backgroundColor: C.surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: C.hairline,
  },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  right: { alignItems: "flex-end", gap: 4 },
  noPlate: { color: C.steel, fontFamily: "monospace" },
  kindBadge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  kindText: { color: "#fff", fontSize: 9, fontWeight: "700", letterSpacing: 0.5 },
  time: { color: C.steel, fontSize: 10 },
  meta: { flexDirection: "row", marginTop: 6, flexWrap: "wrap" },
  metaText: { color: C.steel, fontSize: 11 },
  metaDot: { color: C.hairline, fontSize: 11 },
});
