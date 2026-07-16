"""Thin wrapper around woolies-nz-cli WoolworthsClient."""

from __future__ import annotations

import asyncio
from typing import Any

from shared.models import ProductMatch


class WoolworthsError(Exception):
    """Raised when Woolworths operations fail."""


def _is_auth_failure(exc: BaseException) -> bool:
    """True when Woolworths rejected the session (cookies expired, login failed)."""
    from woolies_cli.http_client import CookieExpiredError

    if isinstance(exc, CookieExpiredError):
        return True
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "cookie",
            "authentication failed",
            "email step failed",
            "password step failed",
            "no saved cookies",
            "autherror",
        )
    )


WOOLWORTHS_BASE_URL = "https://www.woolworths.co.nz"
# Woolworths NZ trolley page (header cart icon links here). /shop/shopping/basket 404s.
WOOLWORTHS_CART_URL = f"{WOOLWORTHS_BASE_URL}/reviewtrolley"
WOOLWORTHS_CART_URL_FALLBACK = f"{WOOLWORTHS_BASE_URL}/shop"


class WoolworthsAdapter:
    """Async adapter for Woolworths NZ search and cart operations."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._client = None
        self._label_cache: dict[str, Any] = {}

    def _get_client(self):
        if self._client is None:
            from woolies_cli.client import WoolworthsClient

            self._client = WoolworthsClient(headless=self.headless)
        return self._client

    async def _http_get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float = 12.0,
    ) -> dict[str, Any]:
        """Direct HTTP GET — avoids woolies-cli Camoufox refresh on auth failure."""
        from woolies_cli.http_client import HTTPClient

        try:
            return await asyncio.wait_for(
                HTTPClient().get(path, params=params),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise WoolworthsError(f"Request timed out: {path}") from exc
        except Exception as exc:
            raise WoolworthsError(str(exc)) from exc

    async def _http_post(
        self,
        path: str,
        data: dict[str, Any],
        *,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        from woolies_cli.http_client import HTTPClient

        try:
            return await asyncio.wait_for(
                HTTPClient().post(path, data=data),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise WoolworthsError(f"Request timed out: {path}") from exc
        except Exception as exc:
            raise WoolworthsError(str(exc)) from exc

    async def _http_delete(self, path: str, *, timeout: float = 30.0) -> dict[str, Any]:
        from woolies_cli.http_client import HTTPClient

        try:
            return await asyncio.wait_for(HTTPClient().delete(path), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise WoolworthsError(f"Request timed out: {path}") from exc
        except Exception as exc:
            raise WoolworthsError(str(exc)) from exc

    @staticmethod
    def product_url(sku: str, product_name: str = "") -> str:
        from urllib.parse import quote_plus

        if sku and sku not in ("OFFLINE", "PANTRY"):
            return f"{WOOLWORTHS_BASE_URL}/shop/productdetails?stockcode={sku}"
        if product_name:
            return f"{WOOLWORTHS_BASE_URL}/shop/search?searchTerm={quote_plus(product_name)}"
        return WOOLWORTHS_BASE_URL

    async def get_product_raw(self, sku: str, *, timeout: float = 12.0) -> dict[str, Any]:
        """Full product JSON from Woolworths (includes ingredients/allergens)."""
        try:
            return await self._http_get(f"/api/v1/products/{sku}", timeout=timeout)
        except WoolworthsError:
            raise
        except Exception as exc:
            raise WoolworthsError(f"Product fetch failed for SKU {sku}: {exc}") from exc

    async def get_product_match(self, sku: str, *, timeout: float = 12.0) -> ProductMatch | None:
        """Resolve a known stockcode to a ProductMatch (search bypass)."""
        try:
            item = await self.get_product_raw(sku, timeout=timeout)
        except WoolworthsError:
            return None
        price = item.get("price") or {}
        size = item.get("size") or {}
        unit = item.get("unit") or "Each"
        if unit == "Kg":
            unit = "Kilogram"
        raw = {
            "name": item.get("name") or "",
            "brand": item.get("brand") or "",
            "sku": str(item.get("sku") or sku),
            "price": price.get("originalPrice", 0),
            "sale_price": price.get("salePrice"),
            "is_special": bool(price.get("isSpecial")),
            "unit": unit,
            "size": size.get("volumeSize") or "",
            "cup_price": size.get("cupPrice"),
            "cup_measure": size.get("cupMeasure"),
            "in_stock": item.get("availabilityStatus") == "In Stock",
            "category": (
                (item.get("departments") or [{}])[0].get("name", "")
                if item.get("departments")
                else item.get("breadcrumb", {}).get("department", {}).get("name", "")
            ),
        }
        match = self._to_match(raw)
        return match if match.sku and match.product_name else None

    async def get_product_label(self, sku: str):
        """Parsed ingredients/allergens for a SKU (cached per adapter instance)."""
        from shared.gluten_label import ProductLabelInfo
        from woolworths_adapter.product_labels import parse_product_label

        if sku in self._label_cache:
            return self._label_cache[sku]
        try:
            raw = await self.get_product_raw(sku)
            label = parse_product_label(raw)
        except WoolworthsError:
            label = ProductLabelInfo()
        self._label_cache[sku] = label
        return label

    @staticmethod
    def _to_match(raw: dict[str, Any]) -> ProductMatch:
        price = float(raw.get("sale_price") or raw.get("price") or 0)
        unit = raw.get("unit") or "Each"
        if unit == "Kg":
            unit = "Kilogram"
        return ProductMatch(
            sku=str(raw.get("sku") or ""),
            product_name=str(raw.get("name") or ""),
            brand=str(raw.get("brand") or ""),
            size=str(raw.get("size") or ""),
            unit_price=price,
            sale_price=float(raw["sale_price"]) if raw.get("sale_price") else None,
            is_special=bool(raw.get("is_special")),
            unit=unit if unit in ("Each", "Kilogram") else "Each",
            in_stock=bool(raw.get("in_stock", True)),
            category=str(raw.get("category") or ""),
            cup_price=float(raw["cup_price"]) if raw.get("cup_price") else None,
            cup_measure=raw.get("cup_measure"),
        )

    async def search(self, query: str, limit: int = 10) -> list[ProductMatch]:
        try:
            size = min(max(1, limit), 48)
            result = await self._http_get(
                "/api/v1/products",
                params={
                    "target": "search",
                    "search": query,
                    "inStockProductsOnly": "false",
                    "size": str(size),
                },
            )
            matches: list[ProductMatch] = []
            for item in result.get("products", {}).get("items", []):
                if item.get("type") != "Product":
                    continue
                try:
                    raw = {
                        "name": item.get("name") or "",
                        "brand": item.get("brand") or "",
                        "sku": str(item.get("sku", "")),
                        "price": item.get("price", {}).get("originalPrice", 0),
                        "sale_price": item.get("price", {}).get("salePrice"),
                        "is_special": item.get("price", {}).get("isSpecial", False),
                        "unit": item.get("unit", "Each"),
                        "size": item.get("size", {}).get("volumeSize", ""),
                        "cup_price": item.get("size", {}).get("cupPrice"),
                        "cup_measure": item.get("size", {}).get("cupMeasure"),
                        "in_stock": item.get("availabilityStatus") == "In Stock",
                        "category": (
                            (item.get("departments") or [{}])[0].get("name", "")
                            if item.get("departments")
                            else item.get("breadcrumb", {}).get("department", {}).get("name", "")
                        ),
                    }
                    match = self._to_match(raw)
                    if match.sku and match.product_name:
                        matches.append(match)
                except Exception:
                    continue
            return matches[:limit]
        except WoolworthsError:
            raise
        except Exception as exc:
            raise WoolworthsError(f"Search failed for '{query}': {exc}") from exc

    @staticmethod
    def is_auth_failure(exc: BaseException) -> bool:
        return _is_auth_failure(exc)

    async def validate_session(self, *, retries: int = 3, timeout: float = 12.0) -> bool:
        """Ping the live trolley API — cookie file alone is not enough."""
        for attempt in range(retries):
            try:
                await self._http_get("/api/v1/trolleys/my", timeout=timeout)
                return True
            except WoolworthsError:
                if attempt < retries - 1:
                    await asyncio.sleep(1.5 * (attempt + 1))
        return False

    async def probe_search(self, *, timeout: float = 12.0) -> bool:
        """Lightweight check that product search works."""
        try:
            result = await self._http_get(
                "/api/v1/products",
                params={
                    "target": "search",
                    "search": "milk",
                    "inStockProductsOnly": "false",
                    "size": "1",
                },
                timeout=timeout,
            )
            items = result.get("products", {}).get("items", [])
            return any(item.get("type") == "Product" for item in items)
        except WoolworthsError:
            return False

    async def is_live(self) -> bool:
        """True when session + search both work."""
        if not await self.validate_session():
            return False
        return await self.probe_search()

    async def _post_cart_item(
        self, sku: str, quantity: float, unit: str
    ) -> dict[str, Any]:
        """Add to trolley via API without prefetching product (avoids 404 on stale SKUs)."""
        return await self._http_post(
            "/api/v1/trolleys/my/items",
            data={"sku": sku, "quantity": str(quantity), "pricingUnit": unit},
        )

    async def get_cart_skus(self) -> set[str]:
        """Return SKUs currently in the Woolworths trolley."""
        cart = await self.get_cart()
        skus: set[str] = set()
        for category in cart.get("items", []):
            for product in category.get("products", []):
                sku = product.get("sku")
                if sku is not None:
                    skus.add(str(sku))
        return skus

    async def add_to_cart(
        self,
        sku: str,
        quantity: float,
        unit: str = "Each",
        *,
        retries: int = 2,
    ) -> dict[str, Any]:
        # Woolworths API expects "Kg" not "Kilogram"
        if unit == "Kilogram":
            unit = "Kg"

        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                result = await self._post_cart_item(sku, quantity, unit)
                await asyncio.sleep(0.3)
                return result
            except Exception as exc:
                last_exc = exc
                if _is_auth_failure(exc):
                    raise WoolworthsError(
                        f"Session expired while adding SKU {sku}. "
                        "Run: meal-agent login"
                    ) from exc
                msg = str(exc).lower()
                if "404" in msg and attempt < retries - 1:
                    # SKU may be store-specific; retry once after brief pause
                    await asyncio.sleep(1.0)
                    continue
                if attempt < retries - 1:
                    await asyncio.sleep(1.0)
        raise WoolworthsError(f"Cart add failed for SKU {sku}: {last_exc}") from last_exc

    async def get_cart_subtotal(self) -> float | None:
        """Return cart subtotal from live trolley if available."""
        try:
            cart = await self.get_cart()
            totals = cart.get("context", {}).get("basketTotals", {})
            subtotal = totals.get("subtotal")
            if isinstance(subtotal, str):
                return float(subtotal.replace("$", "").replace(",", "").strip())
            all_products = []
            for category in cart.get("items", []):
                all_products.extend(category.get("products", []))
            if not all_products:
                return 0.0
            total = 0.0
            for product in all_products:
                price = product.get("price", {})
                qty = product.get("quantity", {}).get("value", 0)
                unit_price = float(price.get("originalPrice", 0) or 0)
                total += unit_price * float(qty)
            return round(total, 2)
        except Exception:
            return None

    async def get_cart(self, *, timeout: float = 15.0) -> dict[str, Any]:
        return await self._http_get("/api/v1/trolleys/my", timeout=timeout)

    async def clear_cart(self) -> dict[str, Any]:
        """Remove all items from the Woolworths trolley (DELETE /api/v1/trolleys/my/items)."""
        try:
            result = await self._http_delete("/api/v1/trolleys/my/items", timeout=45.0)
            return result if isinstance(result, dict) else {"message": "Cart cleared"}
        except WoolworthsError as exc:
            msg = str(exc).lower()
            if "400" in msg or "bad request" in msg:
                try:
                    skus = await self.get_cart_skus()
                    if not skus:
                        return {"message": "Cart is already empty"}
                except WoolworthsError:
                    pass
            raise

    async def is_session_available(self) -> bool:
        return await self.is_live()
