from typing import Any, Union

import redis

BALANCES_KEY_TEMPLATE = "{address}_{symbol}"


def store_hash_set(
    _hash: str,
    key: str,
    value: Any,
    provider: Union[redis.Redis, redis.client.Pipeline],
):
    provider.hset(_hash, key, value)


def store_asset_hist_balance(
    treasury_address: str,
    symbol: str,
    asset_hist_balance_json: str,
    provider: Union[redis.Redis, redis.client.Pipeline],
):
    store_hash_set(
        "balances",
        BALANCES_KEY_TEMPLATE.format(address=treasury_address, symbol=symbol),
        asset_hist_balance_json,
        provider,
    )


def store_asset_hist_performance(
    symbol: str,
    asset_hist_performance_json: str,
    provider: Union[redis.Redis, redis.client.Pipeline],
):
    store_hash_set(
        "asset_hist_performance", symbol, asset_hist_performance_json, provider
    )


def store_asset_correlations(
    address: str,
    asset_correlations_json: str,
    provider: Union[redis.Redis, redis.client.Pipeline],
):
    store_hash_set("asset_correlations", address, asset_correlations_json, provider)
