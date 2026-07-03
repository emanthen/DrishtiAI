import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { api } from "./api";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerPushToken(authToken: string): Promise<void> {
  if (Platform.OS === "web") return;

  const { status: existing } = await Notifications.getPermissionsAsync();
  let final = existing;
  if (existing !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync();
    final = status;
  }
  if (final !== "granted") return;

  const { data: pushToken } = await Notifications.getExpoPushTokenAsync();
  await api.notifications.register(authToken, pushToken);
}

export async function unregisterPushToken(authToken: string): Promise<void> {
  if (Platform.OS === "web") return;
  try {
    const { data: pushToken } = await Notifications.getExpoPushTokenAsync();
    await api.notifications.unregister(authToken, pushToken);
  } catch {}
}
