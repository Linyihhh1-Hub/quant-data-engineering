from pathlib import Path

import pandas as pd

from quant_data.backtest.simple import run_simple_backtest
from quant_data.storage.parquet import read_parquet, write_parquet


def parse_float_list(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def parse_int_list(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def run_parameter_sensitivity(
    factors: pd.DataFrame,
    daily_bars: pd.DataFrame,
    factor_name: str,
    top_quantiles: list[float],
    rebalance_intervals: list[int],
    transaction_cost: float,
    commission_rate: float,
    slippage_rate: float,
    stamp_tax_rate: float,
    market_sentiment: pd.DataFrame | None = None,
    benchmark_index: pd.DataFrame | None = None,
    sentiment_threshold: float | None = None,
    weak_sentiment_exposure: float = 0.5,
    normal_exposure: float = 1.0,
) -> pd.DataFrame:
    rows = []
    for top_quantile in top_quantiles:
        for rebalance_interval in rebalance_intervals:
            _, metrics = run_simple_backtest(
                factors,
                daily_bars,
                factor_name,
                top_quantile=top_quantile,
                rebalance_interval=rebalance_interval,
                transaction_cost=transaction_cost,
                commission_rate=commission_rate,
                slippage_rate=slippage_rate,
                stamp_tax_rate=stamp_tax_rate,
                market_sentiment=market_sentiment,
                benchmark_index=benchmark_index,
                sentiment_threshold=sentiment_threshold,
                weak_sentiment_exposure=weak_sentiment_exposure,
                normal_exposure=normal_exposure,
            )
            rows.append(
                {
                    "factor_name": factor_name,
                    "top_quantile": top_quantile,
                    "rebalance_interval": rebalance_interval,
                    "total_return": float(metrics.get("total_return", 0.0)),
                    "gross_total_return": float(metrics.get("gross_total_return", 0.0)),
                    "equal_weight_total_return": float(metrics.get("equal_weight_total_return", 0.0)),
                    "hs300_total_return": float(metrics.get("hs300_total_return", 0.0)),
                    "hs300_excess_return": float(metrics.get("hs300_excess_return", 0.0)),
                    "sharpe": float(metrics.get("sharpe", 0.0)),
                    "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
                    "turnover": float(metrics.get("turnover", 0.0)),
                    "total_cost": float(metrics.get("total_cost", 0.0)),
                    "cost_drag": float(metrics.get("cost_drag", 0.0)),
                }
            )
    return pd.DataFrame(rows)


def write_parameter_sensitivity(
    data_dir: str | Path,
    factor_name: str,
    top_quantiles: list[float],
    rebalance_intervals: list[int],
    transaction_cost: float,
    commission_rate: float,
    slippage_rate: float,
    stamp_tax_rate: float,
    sentiment_threshold: float | None = None,
    weak_sentiment_exposure: float = 0.5,
    normal_exposure: float = 1.0,
) -> Path:
    root = Path(data_dir)
    market_sentiment_path = root / "ads" / "market_sentiment_daily.parquet"
    benchmark_index_path = root / "dim" / "hs300_index.parquet"
    market_sentiment = read_parquet(market_sentiment_path) if market_sentiment_path.exists() else None
    benchmark_index = read_parquet(benchmark_index_path) if benchmark_index_path.exists() else None
    result = run_parameter_sensitivity(
        read_parquet(root / "ads" / "factor_wide_daily.parquet"),
        read_parquet(root / "dwd" / "stock_daily.parquet"),
        factor_name,
        top_quantiles,
        rebalance_intervals,
        transaction_cost,
        commission_rate,
        slippage_rate,
        stamp_tax_rate,
        market_sentiment=market_sentiment,
        benchmark_index=benchmark_index,
        sentiment_threshold=sentiment_threshold,
        weak_sentiment_exposure=weak_sentiment_exposure,
        normal_exposure=normal_exposure,
    )
    return write_parquet(result, root / "ads" / "parameter_sensitivity.parquet")
