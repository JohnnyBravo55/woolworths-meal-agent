/** Dynamic Expo config — supports GitHub Pages base path via EXPO_PUBLIC_BASE_URL. */
const appJson = require("./app.json");

const baseUrl = (process.env.EXPO_PUBLIC_BASE_URL || "").replace(/\/$/, "");

module.exports = {
  ...appJson.expo,
  experiments: {
    ...(appJson.expo.experiments || {}),
    ...(baseUrl ? { baseUrl } : {}),
  },
  extra: {
    ...(appJson.expo.extra || {}),
    apiUrl: process.env.EXPO_PUBLIC_API_URL || "",
    accessGate: process.env.EXPO_PUBLIC_ACCESS_GATE || "",
  },
};
