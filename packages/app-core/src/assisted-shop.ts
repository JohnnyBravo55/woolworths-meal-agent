/** Client helpers for assisted multi-store shopping. */

import type { PriceCheckLine, StoreChain, StoreRef } from "./types";

const WW_BASE = "https://www.woolworths.co.nz";
const FOODSTUFFS_WEB: Record<"new_world" | "paknsave", string> = {
  new_world: "https://www.newworld.co.nz",
  paknsave: "https://www.paknsave.co.nz",
};

function encode(q: string): string {
  return encodeURIComponent(q.trim());
}

export function storeShopUrl(store: StoreRef): string {
  if (store.store_url) return store.store_url;
  if (store.chain === "woolworths") return WW_BASE;
  if (store.chain === "new_world" || store.chain === "paknsave") {
    return FOODSTUFFS_WEB[store.chain];
  }
  if (store.chain === "freshchoice") {
    const slug = store.id.split(":")[1] || "";
    return slug ? `https://${slug}.store.freshchoice.co.nz` : "https://store.freshchoice.co.nz";
  }
  return "";
}

export function lineProductUrl(store: StoreRef, line: PriceCheckLine): string {
  if (line.product_url) return line.product_url;
  const sku = (line.sku || "").trim();
  if (store.chain === "woolworths" && sku && sku !== "OFFLINE" && sku !== "PANTRY") {
    return `${WW_BASE}/shop/productdetails?stockcode=${encode(sku)}`;
  }
  if ((store.chain === "new_world" || store.chain === "paknsave") && sku) {
    return `${FOODSTUFFS_WEB[store.chain]}/shop/product/${encode(sku)}`;
  }
  return "";
}

export function lineSearchUrl(store: StoreRef, line: PriceCheckLine): string {
  if (line.search_url) return line.search_url;
  const q = (line.product_name || line.ingredient || "").trim();
  if (store.chain === "woolworths") {
    return q ? `${WW_BASE}/shop/search?searchTerm=${encode(q)}` : WW_BASE;
  }
  if (store.chain === "new_world" || store.chain === "paknsave") {
    const base = FOODSTUFFS_WEB[store.chain];
    return q ? `${base}/shop/search?q=${encode(q)}` : base;
  }
  if (store.chain === "freshchoice") {
    const host = storeShopUrl(store);
    return q ? `${host}/search?q=${encode(q)}` : host;
  }
  return "";
}

export function lineCopyText(line: PriceCheckLine): string {
  const name = (line.product_name || line.ingredient || "").trim();
  const qty =
    line.quantity && line.quantity !== 1
      ? `${line.quantity}${line.unit ? ` ${line.unit}` : ""}`
      : "";
  return qty ? `${name} (${qty})` : name;
}

export function lineBoughtKey(storeId: string, ingredient: string, index: number): string {
  return `${storeId}::${ingredient}::${index}`;
}

export function chainLabel(chain: StoreChain): string {
  switch (chain) {
    case "woolworths":
      return "Woolworths";
    case "paknsave":
      return "Pak'nSave";
    case "new_world":
      return "New World";
    case "freshchoice":
      return "FreshChoice";
    default:
      return chain;
  }
}
