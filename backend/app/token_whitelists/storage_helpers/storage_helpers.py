from typing import Union

import redis

CHAIN_ID = 1


def store_token_whitelist(
    address: list[str], provider: Union[redis.Redis, redis.client.Pipeline]
):
    provider.sadd("whitelist", *address)


def retrieve_token_whitelist(
    provider: Union[redis.Redis, redis.client.Pipeline]
) -> list[str]:
    return provider.smembers("whitelist")
