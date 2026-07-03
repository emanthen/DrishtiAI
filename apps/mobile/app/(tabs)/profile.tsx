import { Pressable, StyleSheet, Text, View } from "react-native";
import { api } from "@/lib/api";
import { clearToken, useAuthStore } from "@/lib/store";
import { unregisterPushToken } from "@/lib/notifications";

const C = {
  ink: "#0B0F14",
  surface: "#151B23",
  bone: "#F1F5F9",
  steel: "#64748B",
  signal: "#3B82F6",
  alert: "#EF4444",
  hairline: "#1E293B",
};

export default function ProfileScreen() {
  const token = useAuthStore((s) => s.token)!;
  const user = useAuthStore((s) => s.user);

  async function handleLogout() {
    try { await unregisterPushToken(token); } catch {}
    try { await api.auth.logout(token); } catch {}
    await clearToken();
  }

  return (
    <View style={styles.root}>
      <View style={styles.card}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {user?.name?.charAt(0).toUpperCase() ?? "?"}
          </Text>
        </View>
        <Text style={styles.name}>{user?.name ?? "—"}</Text>
        <Text style={styles.email}>{user?.email ?? "—"}</Text>
        <View style={styles.roleBadge}>
          <Text style={styles.roleText}>{user?.role ?? "—"}</Text>
        </View>
      </View>

      <Pressable style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>Sign out</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.ink, padding: 24 },
  card: {
    backgroundColor: C.surface,
    borderRadius: 16,
    padding: 28,
    alignItems: "center",
    borderWidth: 1,
    borderColor: C.hairline,
    marginBottom: 24,
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: C.signal,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 16,
  },
  avatarText: { color: "#fff", fontSize: 32, fontWeight: "700" },
  name: { color: C.bone, fontSize: 20, fontWeight: "700", marginBottom: 4 },
  email: { color: C.steel, fontSize: 14, marginBottom: 12 },
  roleBadge: {
    backgroundColor: C.ink,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: C.hairline,
  },
  roleText: { color: C.steel, fontSize: 12, textTransform: "uppercase", fontWeight: "600" },
  logoutBtn: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: C.alert,
    borderRadius: 10,
    padding: 16,
    alignItems: "center",
  },
  logoutText: { color: C.alert, fontWeight: "700", fontSize: 15 },
});
