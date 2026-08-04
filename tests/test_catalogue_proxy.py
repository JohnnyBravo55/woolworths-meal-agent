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
async def test_search_public_catalogue_direct_without_proxy(monkeypatch):
    monkeypatch.delenv("WOOLWORTHS_CATALOGUE_PROXY_URL", raising=False)
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
