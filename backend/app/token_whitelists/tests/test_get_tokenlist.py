from json import loads
from json.decoder import JSONDecodeError

import pytest
from fakeredis import FakeRedis
from httpx import AsyncClient

from backend.app.token_whitelists import (
    get_processed_tokenlists,
    maybe_populate_whitelist,
    store_and_get_tokenlist_whitelist,
)

from .conftest import (
    HTTPStatusError,
    raise_http_status_error_404,
    raise_http_status_error_501,
)


class MockResponse:
    status_code = None

    def raise_for_status(self):
        return None

    @staticmethod
    def json():
        return {
            "name": "MockGecko",
            "logoURI": "https://www.mockgecko.com/mock/path/thumb.jpg",
            "keywords": ["mockfi"],
            "timestamp": "2022-06-19T11:08:16.098+00:00",
            "tokens": [
                {"chainId": 1, "address": "0x6d6f636b5f31"},
                {"chainId": 1, "address": "0x6d6f636b5f32"},
            ],
        }


async def mock_get_tokenlist(*_):
    return MockResponse()


@pytest.mark.asyncio
async def test_get_tokenlists_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(AsyncClient, "get", mock_get_tokenlist)

    mocked_provider = FakeRedis(decode_responses=True)

    await store_and_get_tokenlist_whitelist(mocked_provider)
    assert mocked_provider.smembers("whitelist") == {
        "0x6d6f636b5f31",
        "0x6d6f636b5f32",
        "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",  # Native ETH should always be whitelisted
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "json_resp",
    [
        lambda _: {
            "name": "MockGecko",
            "logoURI": "https://www.mockgecko.com/mock/path/thumb.jpg",
            "keywords": ["mockfi"],
            "timestamp": "2022-06-19T11:08:16.098+00:00",
            "tokens": [
                {"chainId": 1, "address": "0x6d6f636b5f31"},
                {"chainId": 1},
            ],
        },
        lambda _: {
            "name": "MockGecko",
            "logoURI": "https://www.mockgecko.com/mock/path/thumb.jpg",
            "keywords": ["mockfi"],
            "timestamp": "2022-06-19T11:08:16.098+00:00",
            "tokens": [
                {"address": "0x6d6f636b5f31"},
                {"chainId": 1, "address": "0x6d6f636b5f32"},
            ],
        },
        lambda _: {
            "name": "MockGecko",
            "logoURI": "https://www.mockgecko.com/mock/path/thumb.jpg",
            "keywords": ["mockfi"],
            "timestamp": "2022-06-19T11:08:16.098+00:00",
            "toekns": [
                {"chainId": 1, "address": "0x6d6f636b5f31"},
                {"chainId": 1, "address": "0x6d6f636b5f32"},
            ],
        },
    ],
)
async def test_get_tokenlists_bad_resp_json(monkeypatch: pytest.MonkeyPatch, json_resp):
    async def async_return(*_):
        return MockResponse()

    url = "https://tokens.coingecko.com/uniswap/all.json"
    monkeypatch.setattr(AsyncClient, "get", async_return)
    monkeypatch.setattr(MockResponse, "json", json_resp)
    with pytest.raises(KeyError):
        await get_processed_tokenlists(url)


@pytest.mark.asyncio
async def test_maybe_populate_whitelist_success_preprop(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "backend.app.token_whitelists.whitelists.retrieve_token_whitelist",
        lambda _: ["0x6d6f636b5f746f6b656e5f31", "0x6d6f636b5f746f6b656e5f32"],
        raising=True,
    )
    mocked_whitelist = await maybe_populate_whitelist("mocked_provider")
    assert mocked_whitelist == [
        "0x6d6f636b5f746f6b656e5f31",
        "0x6d6f636b5f746f6b656e5f32",
    ]


@pytest.mark.asyncio
async def test_get_tokenlists_resp_err_404(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(AsyncClient, "get", mock_get_tokenlist)
    monkeypatch.setattr(MockResponse, "status_code", 404)
    monkeypatch.setattr(MockResponse, "raise_for_status", raise_http_status_error_404)

    url = "https://tokens.coingecko.com/uniswap/all.json"
    with pytest.raises(HTTPStatusError) as error:
        await get_processed_tokenlists(url)

        assert "mocked http status error" in str(error.value)


@pytest.mark.asyncio
async def test_get_tokenlists_resp_err_5xx(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(AsyncClient, "get", mock_get_tokenlist)
    monkeypatch.setattr(MockResponse, "status_code", 501)
    monkeypatch.setattr(MockResponse, "raise_for_status", raise_http_status_error_501)

    url = "https://tokens.coingecko.com/uniswap/all.json"
    with pytest.raises(HTTPStatusError) as error:
        await get_processed_tokenlists(url)

        assert "mocked http status error" in str(error.value)


@pytest.mark.asyncio
async def test_get_tokenlists_json_err(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(AsyncClient, "get", mock_get_tokenlist)
    monkeypatch.setattr(MockResponse, "json", lambda _: loads("bad json response"))

    url = "https://tokens.coingecko.com/uniswap/all.json"
    with pytest.raises(JSONDecodeError):
        await get_processed_tokenlists(url)
