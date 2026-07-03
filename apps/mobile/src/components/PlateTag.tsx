import { StyleSheet, Text, View } from "react-native";

const COLORS = {
  ink: "#0B0F14",
  bone: "#F1F5F9",
  signal: "#3B82F6",
  hairline: "#1E293B",
};

interface Props {
  plate: string;
  size?: "sm" | "md";
}

export function PlateTag({ plate, size = "md" }: Props) {
  return (
    <View style={[styles.tag, size === "sm" && styles.tagSm]}>
      <Text style={[styles.text, size === "sm" && styles.textSm]}>
        {plate.toUpperCase()}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: {
    backgroundColor: COLORS.ink,
    borderWidth: 1,
    borderColor: COLORS.signal,
    borderRadius: 4,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  tagSm: {
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  text: {
    color: COLORS.bone,
    fontFamily: "monospace",
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 2,
  },
  textSm: {
    fontSize: 11,
    letterSpacing: 1,
  },
});
