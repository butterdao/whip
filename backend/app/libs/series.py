import pandas as pd

from ..treasury.models import Price


def make_hist_price_series(
    token_symbol: str,
    prices: list[Price],
) -> pd.Series:
    return pd.Series(
        (price.value for price in prices),
        index=pd.Index((price.timestamp for price in prices), name="timestamp"),
        name=f"{token_symbol} historical price",
    ).sort_index()
