import { Tabs } from "expo-router";
import { useEffect } from "react";
import { useAuthStore } from "@/lib/store";
import { registerPushToken } from "@/lib/notifications";

const C = {
  ink: "#0B0F14",
  surface: "#151B23",
  bone: "#F1F5F9",
  steel: "#64748B",
  signal: "#3B82F6",
  hairline: "#1E293B",
};

export default function TabLayout() {
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (token) registerPushToken(token).catch(() => {});
  }, [token]);

  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: C.surface },
        headerTintColor: C.bone,
        headerTitleStyle: { fontWeight: "700" },
        tabBarStyle: { backgroundColor: C.surface, borderTopColor: C.hairline },
        tabBarActiveTintColor: C.signal,
        tabBarInactiveTintColor: C.steel,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Home", tabBarLabel: "Home" }}
      />
      <Tabs.Screen
        name="passes"
        options={{ title: "Visitor Passes", tabBarLabel: "Passes" }}
      />
      <Tabs.Screen
        name="alerts"
        options={{ title: "Alerts", tabBarLabel: "Alerts" }}
      />
      <Tabs.Screen
        name="profile"
        options={{ title: "Profile", tabBarLabel: "Profile" }}
      />
    </Tabs>
  );
}
