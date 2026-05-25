from pathlib import Path

import pandas as pd

from quant_data.backtest.simple import run_simple_backtest
from quant_data.storage.parquet import read_parquet, write_parquet

COST_SCENARIOS = {
    "no_cost": {"commission_rate": 0.0, "stamp_tax_rate": 0.0, "slippage_rate": 0.0},
    "low_cost": {"commission_rate": 0.0001, "stamp_tax_rate": 0.0005, "slippage_rate": 0.0002},
    "default_cost": {"commission_rate": 0.0003, "stamp_tax_rate": 0.0005, "slippage_rate": 0.0005},
    "high_cost": {"commission_rate": 0.0005, "stamp_tax_rate": 0.001, "slippage_rate": 0.001},
}


def run_cost_sensitivity(
    factors: pd.DataFrame,
    daily_bars: pd.DataFrame,
    factor_name: str,
    factor_direction: str,
    top_quantile: float,
    rebalance_interval: int,
    market_sentiment: pd.DataFrame | None = None,
    benchmark_index: pd.DataFrame | None = None,
    sentiment_threshold: float | None = None,
    sentiment_mode: str = "step",
    sentiment_smooth_alpha: float = 0.2,
    min_exposure: float = 0.3,
    max_exposure: float = 1.0,
    base_exposure: float = 0.6,
    sentiment_scale: float = 0.2,
    weak_sentiment_exposure: float = 0.5,
    normal_exposure: float = 1.0,
    min_amount: float | None = None,
    min_volume: float | None = None,
    exclude_st: bool = False,
) -> pd.DataFrame:
    rows = []
    for scenario, costs in COST_SCENARIOS.items():
        _, metrics = run_simple_backtest(
            factors,
            daily_bars,
            factor_name,
            top_quantile=top_quantile,
            rebalance_interval=rebalance_interval,
            factor_direction=factor_direction,
            transaction_cost=0.0,
            commission_rate=costs["commission_rate"],
            stamp_tax_rate=costs["stamp_tax_rate"],
            slippage_rate=costs["slippage_rate"],
            market_sentiment=market_sentiment,
            benchmark_index=benchmark_index,
            sentiment_threshold=sentiment_threshold,
            sentiment_mode=sentiment_mode,
            sentiment_smooth_alpha=sentiment_smooth_alpha,
            min_exposure=min_exposure,
            max_exposure=max_exposure,
            base_exposure=base_exposure,
            sentiment_scale=sentiment_scale,
            weak_sentiment_exposure=weak_sentiment_exposure,
            normal_exposure=normal_exposure,
            min_amount=min_amount,
            min_volume=min_volume,
            exclude_st=exclude_st,
        )
        rows.append(
            {
                "factor_name": factor_name,
                "factor_direction": factor_direction,
                "cost_scenario": scenario,
                "commission": costs["commission_rate"],
                "stamp_tax": costs["stamp_tax_rate"],
                "slippage": costs["slippage_rate"],
                "total_return": float(metrics.get("total_return", 0.0)),
                "before_cost_total_return": float(metrics.get("gross_total_return", 0.0)),
                "cost_drag": float(metrics.get("cost_drag", 0.0)),
                "cost_to_return": float(metrics.get("cost_to_return", 0.0)),
                "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
                "sharpe": float(metrics.get("sharpe", 0.0)),
                "turnover": float(metrics.get("turnover", 0.0)),
                "min_amount": float(metrics.get("min_amount", 0.0)),
                "min_volume": float(metrics.get("min_volume", 0.0)),
                "exclude_st": float(metrics.get("exclude_st", 0.0)),
            }
        )
    return pd.DataFrame(rows)


def write_cost_sensitivity(
    data_dir: str | Path,
    factor_name: str,
    factor_direction: str,
    top_quantile: float,
    rebalance_interval: int,
    sentiment_threshold: float | None = None,
    sentiment_mode: str = "step",
    sentiment_smooth_alpha: float = 0.2,
    min_exposure: float = 0.3,
    max_exposure: float = 1.0,
    base_exposure: float = 0.6,
    sentiment_scale: float = 0.2,
    weak_sentiment_exposure: float = 0.5,
    normal_exposure: float = 1.0,
    min_amount: float | None = None,
    min_volume: float | None = None,
    exclude_st: bool = False,
) -> Path:
    root = Path(data_dir)
    market_sentiment_path = root / "ads" / "market_sentiment_daily.parquet"
    benchmark_index_path = root / "dim" / "hs300_index.parquet"
    market_sentiment = read_parquet(market_sentiment_path) if market_sentiment_path.exists() else None
    benchmark_index = read_parquet(benchmark_index_path) if benchmark_index_path.exists() else None
    result = run_cost_sensitivity(
        read_parquet(root / "ads" / "factor_wide_daily.parquet"),
        read_parquet(root / "dwd" / "stock_daily.parquet"),
        factor_name,
        factor_direction,
        top_quantile,
        rebalance_interval,
        market_sentiment=market_sentiment,
        benchmark_index=benchmark_index,
        sentiment_threshold=sentiment_threshold,
        sentiment_mode=sentiment_mode,
        sentiment_smooth_alpha=sentiment_smooth_alpha,
        min_exposure=min_exposure,
        max_exposure=max_exposure,
        base_exposure=base_exposure,
        sentiment_scale=sentiment_scale,
        weak_sentiment_exposure=weak_sentiment_exposure,
        normal_exposure=normal_exposure,
        min_amount=min_amount,
        min_volume=min_volume,
        exclude_st=exclude_st,
    )
    return write_parquet(result, root / "ads" / "cost_sensitivity.parquet")
