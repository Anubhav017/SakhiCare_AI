import type { CapacitorConfig } from "@capacitor/cli";

const url = process.env.SAKHICARE_ANDROID_URL;
if (url) {
  const endpoint = new URL(url);
  const emulatorHttp = endpoint.protocol === "http:" && endpoint.hostname === "10.0.2.2";
  if (endpoint.protocol !== "https:" && !emulatorHttp) {
    throw new Error("Use HTTPS or the Android emulator host 10.0.2.2 for local testing.");
  }
}

const config: CapacitorConfig = {
  appId: "ai.sakhicare.mobile",
  appName: "SakhiCare AI",
  webDir: "dist",
  ...(url ? { server: { url, cleartext: new URL(url).protocol === "http:" } } : {}),
};

export default config;
