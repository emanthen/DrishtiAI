import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { api, ApiError } from "@/lib/api";
import { persistToken, useAuthStore } from "@/lib/store";

const C = {
  ink: "#0B0F14",
  surface: "#151B23",
  bone: "#F1F5F9",
  steel: "#64748B",
  signal: "#3B82F6",
  alert: "#EF4444",
  hairline: "#1E293B",
};

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setUser = useAuthStore((s) => s.setUser);

  async function handleLogin() {
    setError(null);
    setLoading(true);
    try {
      const { access_token } = await api.auth.login(email.trim(), password);
      await persistToken(access_token);
      const user = await api.auth.me(access_token);
      setUser(user);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.card}>
        <Text style={styles.logo}>DrishtiAI</Text>
        <Text style={styles.sub}>Secure entry. Smart access.</Text>

        {error && <Text style={styles.error}>{error}</Text>}

        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor={C.steel}
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor={C.steel}
          secureTextEntry
          value={password}
          onChangeText={setPassword}
          onSubmitEditing={handleLogin}
        />

        <Pressable
          style={[styles.btn, loading && styles.btnDisabled]}
          onPress={handleLogin}
          disabled={loading}
        >
          <Text style={styles.btnText}>{loading ? "Signing in…" : "Sign in"}</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.ink, justifyContent: "center", padding: 24 },
  card: { backgroundColor: C.surface, borderRadius: 16, padding: 28, borderWidth: 1, borderColor: C.hairline },
  logo: { color: C.bone, fontSize: 28, fontWeight: "800", textAlign: "center", marginBottom: 4 },
  sub: { color: C.steel, fontSize: 13, textAlign: "center", marginBottom: 28 },
  error: { color: C.alert, fontSize: 13, marginBottom: 12, textAlign: "center" },
  input: {
    backgroundColor: C.ink,
    borderWidth: 1,
    borderColor: C.hairline,
    borderRadius: 8,
    color: C.bone,
    padding: 14,
    marginBottom: 12,
    fontSize: 15,
  },
  btn: { backgroundColor: C.signal, borderRadius: 8, padding: 16, alignItems: "center", marginTop: 4 },
  btnDisabled: { opacity: 0.5 },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 15 },
});
