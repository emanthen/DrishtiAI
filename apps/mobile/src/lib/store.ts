import { create } from "zustand";
import * as SecureStore from "expo-secure-store";

const TOKEN_KEY = "drishti_token";

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  setUser: (user: User) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  token: null,
  user: null,
  setUser: (user) => set({ user }),
  clear: () => set({ token: null, user: null }),
}));

export async function hydrateAuth(): Promise<string | null> {
  const token = await SecureStore.getItemAsync(TOKEN_KEY);
  if (token) useAuthStore.setState({ token });
  return token;
}

export async function persistToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
  useAuthStore.setState({ token });
}

export async function clearToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
  useAuthStore.setState({ token: null, user: null });
}
