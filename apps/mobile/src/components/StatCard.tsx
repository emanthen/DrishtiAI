import { StyleSheet, Text, View } from "react-native";

const COLORS = {
  surface: "#151B23",
  bone: "#F1F5F9",
  steel: "#64748B",
  signal: "#3B82F6",
  confirm: "#22C55E",
  alert: "#EF4444",
  hairline: "#1E293B",
};

interface Props {
  label: string;
  value: string | number;
  accent?: "default" | "alert" | "confirm";
}

export function StatCard({ label, value, accent = "default" }: Props) {
  const accentColor =
    accent === "alert"
      ? COLORS.alert
      : accent === "confirm"
      ? COLORS.confirm
      : COLORS.signal;

  return (
    <View style={[styles.card, { borderTopColor: accentColor }]}>
      <Text style={styles.value}>{value}</Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: COLORS.surface,
    borderRadius: 10,
    borderTopWidth: 3,
    padding: 16,
    flex: 1,
    minWidth: 100,
    borderWidth: 1,
    borderColor: COLORS.hairline,
  },
  value: {
    color: COLORS.bone,
    fontSize: 28,
    fontWeight: "700",
    marginBottom: 4,
  },
  label: {
    color: COLORS.steel,
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.8,
  },
});
