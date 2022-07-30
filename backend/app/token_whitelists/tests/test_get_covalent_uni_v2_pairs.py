from json import loads
from json.decoder import JSONDecodeError
from unittest import mock

import pytest
from fakeredis import FakeRedis
from httpx import AsyncClient

from backend.app.token_whitelists import (
    get_covalent_pair_list,
    get_uniswap_v2_pairs_covalent,
    get_whitelists_from_apis,
    store_and_get_covalent_pairs_whitelist,
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
            "data": {
                "updated_at": "2022-07-10T17:43:01.731Z",
                "items": [
                    {
                        "exchange": "0x6d6f636b5f636f76616c656e745f706169725f31",
                    },
                    {
                        "exchange": "0x6d6f636b5f636f76616c656e745f706169725f32",
                    },
                ],
                "pagination": {
                    "has_more": False,
                    "page_number": 0,
                    "page_size": 2,
                    "total_count": None,
                },
            }
        }


async def mock_get_tokenlist(*_, **__):
    return MockResponse()


@pytest.mark.asyncio
async def test_get_covalent_pair_list_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(AsyncClient, "get", mock_get_tokenlist)
    mocked_provider = FakeRedis(decode_responses=True)

    await store_and_get_covalent_pairs_whitelist(mocked_provider)
    assert mocked_provider.smembers("whitelist") == {
        "0x6d6f636b5f636f76616c656e745f706169725f31",
        "0x6d6f636b5f636f76616c656e745f706169725f32",
    }


@pytest.mark.asyncio
async def test_get_covalent_pair_multipage_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(AsyncClient, "get", mock_get_tokenlist)
    monkeypatch.setattr(
        MockResponse,
        "json",
        mock.Mock(
            side_effect=[
                {
                    "data": {
                        "updated_at": "2022-07-10T17:43:01.731Z",
                        "items": [
                            {
                                "exchange": "0x6d6f636b5f636f76616c656e745f706169725f31",
                            },
                            {
                                "exchange": "0x6d6f636b5f636f76616c656e745f706169725f32",
                            },
                        ],
                        "pagination": {
                            "has_more": True,
                            "page_number": 0,
                            "page_size": 2,
                            "total_count": None,
                        },
                    }
                },
                {
                    "data": {
                        "updated_at": "2022-07-10T17:43:01.731Z",
                        "items": [
                            {
                                "exchange": "0x6d6f636b5f636f76616c656e745f706169725f33",
                            },
                            {
                                "exchange": "0x6d6f636b5f636f76616c656e745f706169725f34",
                            },
                        ],
                        "pagination": {
                            "has_more": False,
                            "page_number": 1,
                            "page_size": 2,
                            "total_count": None,
                        },
                    }
                },
            ]
        ),
    )

    assert await get_whitelists_from_apis([get_uniswap_v2_pairs_covalent]) == [
        "0x6d6f636b5f636f76616c656e745f706169725f31",
        "0x6d6f636b5f636f76616c656e745f706169725f32",
        "0x6d6f636b5f636f76616c656e745f706169725f33",
        "0x6d6f636b5f636f76616c656e745f706169725f34",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "json_resp",
    [
        lambda *_, **__: {"dtaa": {}},
        lambda *_, **__: {
            "data": {
                "updated_at": "2022-07-10T17:43:01.731Z",
                "itms": [],
            }
        },
        lambda *_, **__: {
            "data": {
                "updated_at": "2022-07-10T17:43:01.731Z",
                "items": [
                    {
                        "exchange": "0x6d6f636b5f636f76616c656e745f706169725f31",
                    },
                    {
                        "exchange": "0x6d6f636b5f636f76616c656e745f706169725f32",
                    },
                ],
                "pagnation": {},
            }
        },
        lambda *_, **__: {
            "data": {
                "updated_at": "2022-07-10T17:43:01.731Z",
                "items": [
                    {
                        "exchange": "0x6d6f636b5f636f76616c656e745f706169725f31",
                    },
                    {
                        "exchange": "0x6d6f636b5f636f76616c656e745f706169725f32",
                    },
                ],
                "pagination": {
                    "hs_more": False,
                },
            }
        },
        lambda _: {
            "data": {
                "updated_at": "2022-07-10T17:43:01.731Z",
                "items": [
                    {
                        "exchnge": "0x6d6f636b5f636f76616c656e745f706169725f31",
                    },
                ],
            }
        },
    ],
)
async def test_get_covalent_pair_list_bad_resp_json(
    monkeypatch: pytest.MonkeyPatch, json_resp
):
    async def async_return(*_, **__):
        return MockResponse()

    monkeypatch.setattr(AsyncClient, "get", async_return)
    monkeypatch.setattr(MockResponse, "json", json_resp)
    with pytest.raises(KeyError):
        await get_covalent_pair_list("uniswap_v2")


@pytest.mark.asyncio
async def test_get_covalent_pair_list_resp_err_404(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(AsyncClient, "get", mock_get_tokenlist)
    monkeypatch.setattr(MockResponse, "status_code", 404)
    monkeypatch.setattr(MockResponse, "raise_for_status", raise_http_status_error_404)

    with pytest.raises(HTTPStatusError) as error:
        await get_covalent_pair_list("uniswap_v2")

        assert "mocked http status error" in str(error.value)


@pytest.mark.asyncio
async def test_get_covalent_pair_list_resp_err_5xx(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(AsyncClient, "get", mock_get_tokenlist)
    monkeypatch.setattr(MockResponse, "status_code", 501)
    monkeypatch.setattr(MockResponse, "raise_for_status", raise_http_status_error_501)

    with pytest.raises(HTTPStatusError) as error:
        await get_covalent_pair_list("uniswap_v2")

        assert "mocked http status error" in str(error.value)


@pytest.mark.asyncio
async def test_get_covalent_pair_list_json_err(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(AsyncClient, "get", mock_get_tokenlist)
    monkeypatch.setattr(MockResponse, "json", lambda _: loads("bad json response"))

    with pytest.raises(JSONDecodeError):
        await get_covalent_pair_list("uniswap_v2")
