/**
 * Thin Woolworths NZ catalogue proxy for cloud hosts (Render) blocked by Akamai.
 * Forwards anonymous product search; does not touch cart/login cookies.
 */

const WW = "https://www.woolworths.co.nz";

const WW_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  Accept: "application/json, text/plain, */*",
  "Accept-Language": "en-NZ,en;q=0.9",
  "x-requested-with": "OnlineShopping_Web",
  Origin: WW,
  Referer: `${WW}/`,
};

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Access-Code",
    "Cache-Control": "no-store",
  };
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") || "*";

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }

    if (url.pathname === "/health") {
      return Response.json({ ok: true }, { headers: corsHeaders(origin) });
    }

    if (url.pathname !== "/search" && url.pathname !== "/api/v1/products") {
      return Response.json(
        { error: "Use GET /search?q=milk&size=8" },
        { status: 404, headers: corsHeaders(origin) },
      );
    }

    const q = (url.searchParams.get("q") || url.searchParams.get("search") || "").trim();
    if (!q) {
      return Response.json(
        { error: "Missing q / search" },
        { status: 400, headers: corsHeaders(origin) },
      );
    }

    const size = Math.min(Math.max(Number(url.searchParams.get("size") || "8") || 8, 1), 48);
    const target = new URL(`${WW}/api/v1/products`);
    target.searchParams.set("target", "search");
    target.searchParams.set("search", q);
    target.searchParams.set("inStockProductsOnly", "false");
    target.searchParams.set("size", String(size));

    try {
      // Warm home cookie jar — helps some Akamai challenges.
      const home = await fetch(WW + "/", {
        headers: {
          "User-Agent": WW_HEADERS["User-Agent"],
          Accept: "text/html,application/xhtml+xml",
          "Accept-Language": "en-NZ,en;q=0.9",
        },
        redirect: "follow",
      });
      const cookie = home.headers.getSetCookie?.()?.join("; ") || "";

      const resp = await fetch(target.toString(), {
        headers: {
          ...WW_HEADERS,
          ...(cookie ? { Cookie: cookie } : {}),
        },
        redirect: "follow",
      });

      const body = await resp.text();
      return new Response(body, {
        status: resp.status,
        headers: {
          ...corsHeaders(origin),
          "Content-Type": resp.headers.get("Content-Type") || "application/json",
        },
      });
    } catch (err) {
      return Response.json(
        { error: "Upstream catalogue fetch failed", detail: String(err) },
        { status: 502, headers: corsHeaders(origin) },
      );
    }
  },
};
