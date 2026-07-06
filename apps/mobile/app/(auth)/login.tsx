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
  muted: "#334155",
};

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [showTotp, setShowTotp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setUser = useAuthStore((s) => s.setUser);

  async function attemptLogin(totp?: string) {
    setError(null);
    setLoading(true);
    try {
      // Build request body — totp_code included only when non-empty
      const body: Record<string, string> = { email: email.trim(), password };
      if (totp?.trim()) body.totp_code = totp.trim();

      const res = await fetch(
        `${require("@/lib/api").API_BASE}/auth/login`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      );

      if (!res.ok) {
        const json = await res.json().catch(() => ({}));
        const detail: string = json?.detail ?? res.statusText;

        // If we got a 401 AND we didn't supply a TOTP code AND the user
        // had filled in both email+password, it might be a missing MFA code.
        // Reveal the TOTP field so they can retry.
        if (res.status === 401 && !totp && email.trim() && password) {
          setShowTotp(true);
          setError("Invalid credentials — if your account has 2FA enabled, enter your code below.");
        } else {
          setError(detail);
        }
        return;
      }

      const { access_token } = await res.json();
      await persistToken(access_token);
      const user = await api.auth.me(access_token);
      setUser(user);
    } catch {
      setError("Network error — check your connection and API URL.");
    } finally {
      setLoading(false);
    }
  }

  function handleLogin() {
    if (!email.trim() || !password) {
      setError("Email and password are required.");
      return;
    }
    attemptLogin(showTotp ? totpCode : undefined);
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
          onSubmitEditing={!showTotp ? handleLogin : undefined}
        />

        {showTotp && (
          <View>
            <Text style={styles.totpHint}>6-digit code from your authenticator app</Text>
            <TextInput
              style={[styles.input, styles.totpInput]}
              placeholder="2FA Code"
              placeholderTextColor={C.steel}
              keyboardType="number-pad"
              maxLength={6}
              value={totpCode}
              onChangeText={setTotpCode}
              onSubmitEditing={handleLogin}
              autoFocus
            />
          </View>
        )}

        <Pressable
          style={[styles.btn, loading && styles.btnDisabled]}
          onPress={handleLogin}
          disabled={loading}
        >
          <Text style={styles.btnText}>{loading ? "Signing in…" : "Sign in"}</Text>
        </Pressable>

        {!showTotp && (
          <Pressable style={styles.mfaToggle} onPress={() => setShowTotp(true)}>
            <Text style={styles.mfaToggleText}>I have 2FA enabled →</Text>
          </Pressable>
        )}
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
  totpHint: { color: C.steel, fontSize: 11, marginBottom: 6 },
  totpInput: { letterSpacing: 8, fontSize: 20, textAlign: "center" },
  btn: { backgroundColor: C.signal, borderRadius: 8, padding: 16, alignItems: "center", marginTop: 4 },
  btnDisabled: { opacity: 0.5 },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 15 },
  mfaToggle: { alignItems: "center", marginTop: 16 },
  mfaToggleText: { color: C.muted, fontSize: 12 },
});
