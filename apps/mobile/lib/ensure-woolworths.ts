import { api } from "./api";

export async function isWoolworthsConnected(): Promise<boolean> {
  try {
    const status = await api.getWoolworthsStatus();
    return status.connected;
  } catch {
    return false;
  }
}
