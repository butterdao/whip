import datetime
from dataclasses import asdict, dataclass
from json import loads
from typing import Iterable, Literal, TypeVar, Union

import dateutil
from fastapi import APIRouter, FastAPI, Path
from numpy import NaN
from pytz import UTC

from .spread import build_spread_treasury_with_assets
from .treasury import (
    Balances,
    Prices,
    TotalBalance,
    Treasury,
    build_treasury_with_assets,
)


@dataclass
class PortfolioAsset:
    allocation: float
    volatility: float
    metrics: dict[str, float]
    risk_contribution: float


@dataclass
class PortfolioKpis:
    total_value: float
    volatility: float
    return_vs_market: Union[float, Literal["Infinity"]]


@dataclass
class Portfolio:
    assets: dict[str, PortfolioAsset]
    kpis: PortfolioKpis
    data: dict[str, float]

    @classmethod
    def from_treasury_with_assets(
        cls,
        treasury: Treasury,
        prices: Prices,
        balances: Balances,  # pylint: disable=unused-argument
        total_balance: TotalBalance,
        start: str,
        end: str,
    ):
        histprices = {
            symbol: athp.loc[start:end] for symbol, athp in prices.prices.items()
        }
        totalbalance = total_balance.balance.loc[start:end]

        assets = {
            a.token_symbol: PortfolioAsset(
                allocation=a.balance / treasury.usd_total,
                metrics={}
                if histprices[a.token_symbol][["std_dev", "returns"]].empty
                else loads(
                    histprices[a.token_symbol][["std_dev", "returns"]].to_json(
                        orient="index", date_format="iso"
                    )
                ),
                risk_contribution=a.risk_contribution
                if hasattr(a, "risk_contribution")
                else None,
                volatility=None
                if histprices[a.token_symbol]["std_dev"].mean() is NaN
                else histprices[a.token_symbol]["std_dev"].mean(),
            )
            for a in treasury.assets
        }

        if (start not in totalbalance.index) or (totalbalance.loc[start].balance == 0):
            market_return = "Infinity"
        else:
            eth_series = histprices["ETH"]
            market_return = (
                totalbalance.loc[end].balance - totalbalance.loc[start].balance
            ) / totalbalance.loc[start].balance - (
                eth_series.loc[end].price - eth_series.loc[start].price
            ) / eth_series.loc[
                start
            ].price

        kpis = PortfolioKpis(
            total_value=treasury.usd_total,
            volatility=totalbalance.std_dev.mean(),
            return_vs_market=market_return,
        )

        data = {
            timestamp.to_pydatetime().strftime("%Y-%m-%d"): balance
            for timestamp, balance in totalbalance.to_dict()["balance"].items()
        }
        return cls(assets=assets, kpis=kpis, data=data)


router = APIRouter(prefix="/api")

T = TypeVar("T")


def snake_to_camel_dict_factory(items: Iterable[tuple[str, T]]) -> dict[str, T]:
    def camel(snake_str):
        components = snake_str.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    return {camel(k): v for k, v in items}


@router.get("/portfolio/{address}/{start}")
async def get_portfolio(address: str, start=str):
    end_date = dateutil.utils.today(UTC) - datetime.timedelta(days=1)
    end = end_date.strftime("%Y-%m-%d")

    portfolio = Portfolio.from_treasury_with_assets(
        *(await build_treasury_with_assets(address, 1, start, end)),
        start,
        end,
    )

    return asdict(
        portfolio,
        dict_factory=snake_to_camel_dict_factory,
    )


@router.get(
    "/backtest/spread/{address}/{start}/{token_to_divest_from}/{spread_token}/{percentage}"
)
async def backtest_spread(
    address: str,
    start: str,
    token_to_divest_from: str,
    spread_token: str = Path("USDC", regex="(?:(^USDC$)|(^ETH$))"),
    percentage: int = Path(0, ge=0, le=100),
):
    spread_tokens_metadatas = {
        "USDC": {
            "name": "USD Coin",
            "address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        },
        "ETH": {
            "name": "Ether",
            "address": "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        },
    }

    spread_token_metadata = spread_tokens_metadatas[spread_token]
    end_date = dateutil.utils.today(UTC) - datetime.timedelta(days=1)
    end = end_date.strftime("%Y-%m-%d")

    portfolio = Portfolio.from_treasury_with_assets(
        *(
            await build_spread_treasury_with_assets(
                address,
                1,
                start,
                end,
                token_to_divest_from,
                spread_token_name=spread_token_metadata["name"],
                spread_token_symbol=spread_token,
                spread_token_address=spread_token_metadata["address"],
                spread_percentage=percentage,
            )
        ),
        start,
        end,
    )

    return asdict(
        portfolio,
        dict_factory=snake_to_camel_dict_factory,
    )


app = FastAPI()
app.include_router(router)
