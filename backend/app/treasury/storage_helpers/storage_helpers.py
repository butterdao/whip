import json
from typing import Union

import redis

CHAIN_ID = 1


def store_treasuries_metadata(
    provider: Union[redis.Redis, redis.client.Pipeline],
    addresses: list[Union[str, None]],
    chain_id: int = CHAIN_ID,
):
    payload = [
        json.dumps({"address": address, "chain_id": chain_id}) for address in addresses
    ]
    provider.sadd("treasuries", *payload)


def retrieve_treasuries_metadata(
    provider: Union[redis.Redis, redis.client.Pipeline]
) -> set[tuple[str, int]]:
    treasuries = [
        tuple(json.loads(t).values()) for t in provider.smembers("treasuries")
    ]
    return set(treasuries)
