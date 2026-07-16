import { Platform, StyleSheet } from "react-native";

/** Max content width for Expo web — native phone layouts unchanged. */
export const WEB_PAGE_MAX_WIDTH = 560;

export const webLayout = Platform.OS === "web"
  ? StyleSheet.create({
      page: {
        maxWidth: WEB_PAGE_MAX_WIDTH,
        width: "100%",
        alignSelf: "center",
      },
      main: {
        alignItems: "center",
      },
      header: {
        alignItems: "center",
      },
      title: {
        textAlign: "center",
      },
      actions: {
        alignSelf: "center",
        width: "100%",
        maxWidth: WEB_PAGE_MAX_WIDTH,
        alignItems: "center",
        justifyContent: "center",
      },
    })
  : null;
