"""Catalogue proxy URL wiring for cloud hosts blocked by Woolworths/Akamai."""

from __future__ import annotations

import pytest

from woolworths_adapter.client import (
    WoolworthsAdapter,
    reset_catalogue_circuit_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_circuit():
    reset_catalogue_circuit_for_tests()
    yield
    reset_catalogue_circuit_for_tests()


@pytest.mark.asyncio
async def test_search_public_catalogue_uses_proxy_url(monkeypatch):
    monkeypatch.setenv("WOOLWORTHS_CATALOGUE_PROXY_URL", "https://proxy.example")
    calls: list[tuple[str, dict | None]] = []

    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "products": {
                    "items": [
                        {
                            "type": "Product",
                            "name": "anchor milk standard blue",
                            "sku": "282848",
                            "brand": "anchor",
                            "price": {
                                "originalPrice": 3.73,
                                "salePrice": 3.73,
                                "isSpecial": False,
                            },
                            "unit": "Each",
                            "size": {"volumeSize": "2l"},
                            "availabilityStatus": "In Stock",
                        }
                    ]
                }
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None, headers=None):
            calls.append((url, params))
            return FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    matches = await WoolworthsAdapter().search_public_catalogue("milk", limit=2)
    assert len(matches) == 1
    assert matches[0].sku == "282848"
    assert calls == [("https://proxy.example/search", {"q": "milk", "size": "2"})]


@pytest.mark.asyncio
async def test_search_public_catalogue_defaults_proxy_on_render(monkeypatch):
    monkeypatch.delenv("WOOLWORTHS_CATALOGUE_PROXY_URL", raising=False)
    monkeypatch.setenv("RENDER", "true")
    calls: list[tuple[str, dict | None]] = []

    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "products": {
                    "items": [
                        {
                            "type": "Product",
                            "name": "milk",
                            "sku": "1",
                            "brand": "x",
                            "price": {"originalPrice": 1, "salePrice": 1},
                            "unit": "Each",
                            "size": {},
                            "availabilityStatus": "In Stock",
                        }
                    ]
                }
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None, headers=None):
            calls.append((url, params))
            return FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)
    await WoolworthsAdapter().search_public_catalogue("milk", limit=1)
    assert calls[0][0].endswith("/search")
    assert "workers.dev" in calls[0][0]


@pytest.mark.asyncio
async def test_search_overrides_bypass_circuit_and_network(monkeypatch):
    monkeypatch.delenv("WOOLWORTHS_CATALOGUE_PROXY_URL", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    from shared.models import ProductMatch
    from woolworths_adapter.client import CatalogueUnavailableError, trip_catalogue_circuit

    adapter = WoolworthsAdapter()
    adapter.set_search_overrides(
        {
            "milk": [
                ProductMatch(
                    sku="282848",
                    product_name="anchor milk",
                    brand="anchor",
                    size="2l",
                    unit_price=3.73,
                    unit="Each",
                    in_stock=True,
                )
            ]
        }
    )
    with pytest.raises(CatalogueUnavailableError):
        await trip_catalogue_circuit("forced open")

    calls: list[str] = []

    class BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None, headers=None):
            calls.append(url)
            raise AssertionError("network should not be used when overrides exist")

    monkeypatch.setattr("httpx.AsyncClient", BoomClient)
    matches = await adapter.search("milk", limit=2)
    assert matches[0].sku == "282848"
    assert calls == []


@pytest.mark.asyncio
async def test_search_public_catalogue_direct_without_proxy(monkeypatch):
    monkeypatch.delenv("WOOLWORTHS_CATALOGUE_PROXY_URL", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    calls: list[str] = []

    class FakeResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"products": {"items": []}}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params=None, headers=None):
            calls.append(url)
            return FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    await WoolworthsAdapter().search_public_catalogue("milk", limit=1)
    assert calls == ["https://www.woolworths.co.nz/api/v1/products"]
