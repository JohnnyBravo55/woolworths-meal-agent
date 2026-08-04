# Woolworths catalogue proxy

Cloudflare Worker that forwards anonymous Woolworths NZ product search.
Used by the Render API when datacenter IPs are Akamai-blocked.

## Deploy

```bash
cd infra/ww-catalogue-proxy
npx wrangler login
npx wrangler deploy
```

`render.yaml` currently points at the preview Worker:

`https://ww-catalogue-proxy.copy-begonia.workers.dev`

Claim that temporary Cloudflare account (or redeploy under your own account) so the URL stays live, then update `WOOLWORTHS_CATALOGUE_PROXY_URL` if the hostname changes.

**Hosted web** fetches this Worker from the browser (`prefetchCatalogueViaProxy`) and uploads hits to the API — Render often cannot call `workers.dev` itself (CF bot fight → 403).

Verify:

```
curl https://mealagent.pyxstudio.nz/api/health/catalogue
```

## Endpoints

- `GET /health` — worker up
- `GET /search?q=milk&size=8` — WW product search JSON
