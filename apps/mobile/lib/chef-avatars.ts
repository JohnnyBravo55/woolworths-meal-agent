import type { ImageSourcePropType } from "react-native";

/** Bundled chef portraits — same assets as apps/web/public/chefs. */
const CHEF_AVATARS: Record<string, ImageSourcePropType> = {
  basic_sam: require("../assets/chefs/sam.png"),
  premium_elena: require("../assets/chefs/elena.png"),
  premium_kenji: require("../assets/chefs/kenji.png"),
  premium_moana: require("../assets/chefs/moana.png"),
  premium_alex: require("../assets/chefs/alex.png"),
  premium_amara: require("../assets/chefs/amara.png"),
};

export function chefAvatarSource(chefId: string): ImageSourcePropType | undefined {
  return CHEF_AVATARS[chefId];
}
