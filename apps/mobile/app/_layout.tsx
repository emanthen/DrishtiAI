import { useEffect, useState } from "react";
import { Stack, useRouter, useSegments } from "expo-router";
import { View, ActivityIndicator } from "react-native";
import { hydrateAuth, useAuthStore } from "@/lib/store";
import { api } from "@/lib/api";

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const token = useAuthStore((s) => s.token);
  const setUser = useAuthStore((s) => s.setUser);
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    hydrateAuth().then(async (t) => {
      if (t) {
        try {
          const user = await api.auth.me(t);
          setUser(user);
        } catch {}
      }
      setReady(true);
    });
  }, []);

  useEffect(() => {
    if (!ready) return;
    const inAuth = segments[0] === "(auth)";
    if (!token && !inAuth) router.replace("/(auth)/login");
    if (token && inAuth) router.replace("/(tabs)");
  }, [ready, token, segments]);

  if (!ready) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#0B0F14" }}>
        <ActivityIndicator color="#3B82F6" />
      </View>
    );
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(auth)" />
      <Stack.Screen name="(tabs)" />
    </Stack>
  );
}
