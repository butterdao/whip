import os
from asyncio import gather
from json.decoder import JSONDecodeError
from typing import Any, Coroutine, Generator, Union

import redis
from celery.utils.log import get_task_logger
from httpx import AsyncClient, HTTPStatusError, RequestError, Timeout

from .storage_helpers import retrieve_token_whitelist, store_token_whitelist

COVALENT_KEY = os.getenv("COVALENT_KEY")
COVALENT_POOLS_URL = "https://api.covalenthq.com/v1/{chain_id}/xy=k/{protocol}/pools/"


async def _get_covalent_pair_list(
    protocol: str, chain_id=1
) -> Generator[dict[str, Any], None, None]:
    page_number = 0
    while True:
        async with AsyncClient(
            timeout=Timeout(10.0, read=60.0, connect=90.0)
        ) as client:
            resp = await client.get(
                COVALENT_POOLS_URL.format(chain_id=chain_id, protocol=protocol),
                params={
                    "quote-currency": "USD",
                    "format": "JSON",
                    "page-number": page_number,
                    "page-size": 250,
                    "key": f"ckey_{COVALENT_KEY}",
                },
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            for item in data["items"]:
                yield item
            if not data["pagination"]["has_more"]:
                break
            page_number += 1


async def get_covalent_pair_list(protocol: str, chain_id=1) -> list[str]:
    whitelist = [
        item["exchange"] async for item in _get_covalent_pair_list(protocol, chain_id)
    ]
    return whitelist


async def get_uniswap_v2_pairs_covalent() -> tuple[str, list[str]]:
    datasource = COVALENT_POOLS_URL.format(chain_id=1, protocol="uniswap_v2")
    return (datasource, await get_covalent_pair_list("uniswap_v2"))


async def get_sushiswap_pairs_covalent() -> tuple[str, list[str]]:
    datasource = COVALENT_POOLS_URL.format(chain_id=1, protocol="sushiswap")
    return (datasource, await get_covalent_pair_list("sushiswap"))


async def get_tokenlists(token_list: str) -> list[str]:
    timeout = Timeout(10.0, read=30.0, connect=15.0)
    whitelist = []
    async with AsyncClient(timeout=timeout) as client:
        resp = await client.get(token_list)
        resp.raise_for_status()

        whitelist = [
            token["address"] for token in resp.json()["tokens"] if token["chainId"] == 1
        ]
        # ensure native ETH is always whitelisted
        whitelist.append("0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
    return whitelist


async def get_uniswap_pairs_tokenlists() -> tuple[str, list[str]]:
    path = "jab416171/uniswap-pairtokens/master/uniswap_pair_tokens.json"
    datasource = f"https://raw.githubusercontent.com/{path}"
    return (datasource, await get_tokenlists(datasource))


async def get_coingecko_tokenlists() -> tuple[str, list[str]]:
    datasource = "https://tokens.coingecko.com/uniswap/all.json"
    return (datasource, await get_tokenlists(datasource))


async def get_cmc_tokenlists() -> tuple[str, list[str]]:
    datasource = "https://api.coinmarketcap.com/data-api/v3/uniswap/all.json"
    return (datasource, await get_tokenlists(datasource))


async def get_whitelists_from_apis(_getters: list[Coroutine]) -> list[str]:
    def flatten_2d(input_list: list[list[Any]]) -> list[Any]:
        payload = []
        for sublist in input_list:
            payload.extend(sublist)
        return payload

    return flatten_2d(
        [
            whitelist
            for _, whitelist in await gather(*[_getter() for _getter in _getters])
        ]
    )


async def get_all_covalent_pairs() -> list[str]:
    return await get_whitelists_from_apis(
        [
            get_uniswap_v2_pairs_covalent,
            get_sushiswap_pairs_covalent,
        ]
    )


async def get_all_tokenlists() -> list[str]:
    return await get_whitelists_from_apis(
        [
            get_cmc_tokenlists,
            get_coingecko_tokenlists,
            get_uniswap_pairs_tokenlists,
        ]
    )


async def store_and_get_covalent_pairs_whitelist(
    provider: Union[redis.Redis, redis.client.Pipeline]
) -> list[str]:
    try:
        latest_whitelist = await get_all_covalent_pairs()
    except (HTTPStatusError, RequestError, JSONDecodeError, KeyError) as error:
        logger = get_task_logger(__name__)
        if error.__class__ in [HTTPStatusError, RequestError]:
            logger.error("error receiving pairs from Covalent API", exc_info=error)
            return []
        logger.error(
            "error processing pairs from Covalent API repsonse", exc_info=error
        )
        return []

    store_token_whitelist(latest_whitelist, provider)
    return latest_whitelist


async def store_and_get_tokenlist_whitelist(
    provider: Union[redis.Redis, redis.client.Pipeline]
) -> list[str]:
    try:
        latest_whitelist = await get_all_tokenlists()
    except (HTTPStatusError, RequestError, JSONDecodeError, KeyError) as error:
        logger = get_task_logger(__name__)
        if error.__class__ in [HTTPStatusError, RequestError]:
            logger.error("error receiving token list from API", exc_info=error)
            return []
        logger.error("error processing token list API repsonse", exc_info=error)
        return []

    store_token_whitelist(latest_whitelist, provider)
    return latest_whitelist


async def maybe_populate_whitelist(
    provider: Union[redis.Redis, redis.client.Pipeline]
) -> list[Union[str, None]]:
    latest_whitelist = list(retrieve_token_whitelist(provider))
    if not latest_whitelist:
        latest_whitelist.extend(await store_and_get_tokenlist_whitelist(provider))
        latest_whitelist.extend(await store_and_get_covalent_pairs_whitelist(provider))
    return latest_whitelist
