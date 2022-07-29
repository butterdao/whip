from functools import reduce
from math import isclose

import numpy as np
import pandas as pd

ROLLING_WINDOW_DAYS = 7


def make_returns_df(hist_values: pd.Series, column_name: str) -> pd.DataFrame:
    dataframe = hist_values.to_frame(name=column_name)
    # This returns calculation could be a bit inconsistent when price is 0.
    # We'll consider for now that such a case should not happen 😅.
    dataframe["returns"] = np.log(
        dataframe[column_name] / dataframe[column_name].shift(periods=1)
    )
    dataframe.returns.replace(np.inf, 0, inplace=True)
    dataframe.returns.replace(-np.inf, 0, inplace=True)
    dataframe.returns.iloc[1:].replace(
        np.nan, 0, inplace=True
    )  # Keep first nan (probably useless).
    dataframe["std_dev"] = dataframe.returns.rolling(ROLLING_WINDOW_DAYS).std(ddof=0)
    return dataframe


def _make_returns_matrix(
    token_returns_dfs: dict[str, pd.DataFrame],
    start: str,
    end: str,
):
    """Create a matrix containing the returns for each asset"""
    hist_prices_items = [
        # sorting index before querying by daterange to suppress PD Future Warning
        # ; non-monotonic timeseries issue suppressed
        (
            symbol,
            hist_prices.sort_index().loc[start:end].reset_index(),
        )
        for symbol, hist_prices in token_returns_dfs.items()
        if not hist_prices.sort_index().loc[start:end].empty
    ]

    def reducer_on_symbol_and_hist_prices(
        matrix: pd.DataFrame, symbol_and_hist_prices: tuple[str, pd.DataFrame]
    ) -> pd.DataFrame:
        symbol, hist_prices = symbol_and_hist_prices
        return matrix.merge(
            hist_prices[["timestamp", "returns"]].rename(columns={"returns": symbol}),
            on="timestamp",
        )

    returns_matrix = (
        reduce(
            reducer_on_symbol_and_hist_prices,
            hist_prices_items,
            hist_prices_items[0][1][["timestamp", "returns"]].rename(
                columns={"return": hist_prices_items[0][0]}
            ),
        )
        .drop("returns", axis=1)
        .set_index("timestamp")
    )

    return returns_matrix


# pylint: disable=too-many-locals
def calculate_risk_contributions(
    returns_and_balances: dict[str, tuple[pd.DataFrame, float]],
    start: str,
    end: str,
) -> dict[str, float]:
    returns_matrix = _make_returns_matrix(
        {symbol: rb[0] for symbol, rb in returns_and_balances.items()},
        start,
        end,
    )

    total_balance = sum(rb[1] for rb in returns_and_balances.values())

    weights = np.array(
        [
            np.fromiter(
                (returns_and_balances[symbol][1] for symbol in returns_matrix.columns),
                float,
            )
            / total_balance
        ]
    )

    cov_matrix = returns_matrix.cov()

    std_dev = np.sqrt(weights.dot(cov_matrix).dot(weights.T))

    marginal_contributions = weights.dot(cov_matrix) / std_dev[0][0]
    component_contributions = np.multiply(marginal_contributions, weights)

    summed_component_contributions = np.sum(component_contributions)

    try:
        assert isclose(
            summed_component_contributions, std_dev[0][0], rel_tol=0.0001
        ), "error in calculations"
    except AssertionError:
        return dict(zip(returns_matrix.columns, [None for _ in returns_matrix.columns]))

    component_percentages = component_contributions / std_dev[0][0]

    return dict(zip(returns_matrix.columns, component_percentages[0]))


def make_returns_correlations_matrix(
    token_returns_dfs: dict[str, pd.DataFrame],
    start: str,
    end: str,
):
    returns_matrix = _make_returns_matrix(token_returns_dfs, start, end)

    return returns_matrix.corr()
