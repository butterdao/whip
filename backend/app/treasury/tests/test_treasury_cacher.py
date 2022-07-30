from json import JSONDecodeError, loads

from fakeredis import FakeRedis
from httpx import Client
from pytest import MonkeyPatch, mark, raises

from backend.app.treasury.storage_helpers.storage_helpers import (
    retrieve_treasuries_metadata,
    store_treasuries_metadata,
)
from backend.app.treasury.storage_helpers.treasury_cacher import _get_treasury_list

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
            "success": True,
            "data": [
                {
                    "id": "mock_ns",
                    "bundle": None,
                    "results": {"mocked_tres_portfolios"},
                    "metadata": {
                        "icon": "data:image/svg+xm;base64,mocked_b64_img",
                        "name": "Mock_NS",
                        "website": "mockns.domains.com",
                        "treasuries": [
                            "0x6d6f636b65645f74726561737572795f31",
                            "0x6d6f636b65645f74726561737572795f32",
                            "0x6d6f636b65645f74726561737572795f33",
                        ],
                    },
                }
            ],
        }


def test_get_treasury_list_success(monkeypatch: MonkeyPatch):
    monkeypatch.setattr(Client, "get", lambda *_: MockResponse())

    treasury_list = _get_treasury_list()
    assert treasury_list == [
        "0x6d6f636b65645f74726561737572795f31",
        "0x6d6f636b65645f74726561737572795f32",
        "0x6d6f636b65645f74726561737572795f33",
    ]


def test_get_treasury_list_4xx_err(monkeypatch: MonkeyPatch):
    monkeypatch.setattr(Client, "get", lambda *_: MockResponse())
    monkeypatch.setattr(MockResponse, "status_code", 404)
    monkeypatch.setattr(MockResponse, "raise_for_status", raise_http_status_error_404)

    with raises(HTTPStatusError) as error:
        treasury_list = _get_treasury_list()

        assert not treasury_list
        assert "mocked http status error" in error.value


def test_get_treasury_list_5xx_err(monkeypatch: MonkeyPatch):
    monkeypatch.setattr(Client, "get", lambda *_: MockResponse())
    monkeypatch.setattr(MockResponse, "status_code", 501)
    monkeypatch.setattr(MockResponse, "raise_for_status", raise_http_status_error_501)

    with raises(HTTPStatusError) as error:
        treasury_list = _get_treasury_list()

        assert not treasury_list
        assert "mocked http status error" in error.value


@mark.parametrize(
    "json_resp",
    [
        lambda _: {
            "success": True,
            "dtaa": [{"maybe_good_resp"}],
        },
        lambda _: {
            "success": True,
            "data": [
                {
                    "id": "mock_ns",
                    "bundle": None,
                    "results": {"mocked_tres_portfolios"},
                    "meatdata": {"maybe_good_resp"},
                }
            ],
        },
        lambda _: {
            "success": True,
            "data": [
                {
                    "id": "mock_ns",
                    "bundle": None,
                    "results": {"mocked_tres_portfolios"},
                    "metadata": {
                        "icon": "data:image/svg+xm;base64,mocked_b64_img",
                        "name": "Mock_NS",
                        "website": "mockns.domains.com",
                        "tresries": [
                            "0x6d6f636b65645f74726561737572795f31",
                        ],
                    },
                }
            ],
        },
    ],
)
def test_get_treasury_list_bad_resp_json(monkeypatch: MonkeyPatch, json_resp):
    monkeypatch.setattr(Client, "get", lambda *_: MockResponse())
    monkeypatch.setattr(MockResponse, "json", json_resp)

    with raises(KeyError):
        treasury_list = _get_treasury_list()

        assert not treasury_list


def test_get_treasury_list_json_err(monkeypatch: MonkeyPatch):
    monkeypatch.setattr(Client, "get", lambda *_: MockResponse())
    monkeypatch.setattr(MockResponse, "json", lambda _: loads("bad json response"))

    with raises(JSONDecodeError):
        treasury_list = _get_treasury_list()

        assert not treasury_list


def test_store_and_retrieve_treasury_metadata(monkeypatch: MonkeyPatch):
    monkeypatch.setattr(Client, "get", lambda *_: MockResponse())

    provider = FakeRedis()
    exp_treasuries = {
        ("0x6d6f636b65645f74726561737572795f31", 1),
        ("0x6d6f636b65645f74726561737572795f32", 1),
        ("0x6d6f636b65645f74726561737572795f33", 1),
    }

    store_treasuries_metadata(provider, _get_treasury_list())

    treasuries = retrieve_treasuries_metadata(provider)

    assert treasuries == exp_treasuries
