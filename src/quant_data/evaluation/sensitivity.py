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
    factor_directions: list[str],
    top_quantiles: list[float],
    rebalance_intervals: list[int],
    transaction_cost: float,
    commission_rate: float,
    slippage_rate: float,
    stamp_tax_rate: float,
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
    for factor_direction in factor_directions:
        if factor_direction not in {"top", "bottom"}:
            raise ValueError("factor_direction must be 'top' or 'bottom'")
        for top_quantile in top_quantiles:
            for rebalance_interval in rebalance_intervals:
                _, metrics = run_simple_backtest(
                    factors,
                    daily_bars,
                    factor_name,
                    top_quantile=top_quantile,
                    rebalance_interval=rebalance_interval,
                    factor_direction=factor_direction,
                    transaction_cost=transaction_cost,
                    commission_rate=commission_rate,
                    slippage_rate=slippage_rate,
                    stamp_tax_rate=stamp_tax_rate,
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
                        "top_quantile": top_quantile,
                        "rebalance_interval": rebalance_interval,
                        "total_return": float(metrics.get("total_return", 0.0)),
                        "gross_total_return": float(metrics.get("gross_total_return", 0.0)),
                        "benchmark_total_return": float(metrics.get("equal_weight_total_return", 0.0)),
                        "index_total_return": float(metrics.get("hs300_total_return", 0.0)),
                        "excess_return": float(metrics.get("total_return", 0.0))
                        - float(metrics.get("equal_weight_total_return", 0.0)),
                        "index_excess_return": float(metrics.get("hs300_excess_return", 0.0)),
                        "annualized_return": float(metrics.get("annualized_return", 0.0)),
                        "sharpe": float(metrics.get("sharpe", 0.0)),
                        "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
                        "turnover": float(metrics.get("turnover", 0.0)),
                        "total_cost": float(metrics.get("total_cost", 0.0)),
                        "cost_drag": float(metrics.get("cost_drag", 0.0)),
                        "cost_to_return": float(metrics.get("cost_to_return", 0.0)),
                        "average_exposure": float(metrics.get("average_exposure", 0.0)),
                        "min_amount": float(metrics.get("min_amount", 0.0)),
                        "min_volume": float(metrics.get("min_volume", 0.0)),
                        "exclude_st": float(metrics.get("exclude_st", 0.0)),
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["sharpe", "excess_return", "max_drawdown", "turnover"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def write_parameter_sensitivity(
    data_dir: str | Path,
    factor_names: str | list[str],
    factor_directions: list[str],
    top_quantiles: list[float],
    rebalance_intervals: list[int],
    transaction_cost: float,
    commission_rate: float,
    slippage_rate: float,
    stamp_tax_rate: float,
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
    factor_list = [factor_names] if isinstance(factor_names, str) else factor_names
    factors = read_parquet(root / "ads" / "factor_wide_daily.parquet")
    daily_bars = read_parquet(root / "dwd" / "stock_daily.parquet")
    results = [
        run_parameter_sensitivity(
            factors,
            daily_bars,
            factor_name,
            factor_directions,
            top_quantiles,
            rebalance_intervals,
            transaction_cost,
            commission_rate,
            slippage_rate,
            stamp_tax_rate,
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
        for factor_name in factor_list
    ]
    result = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
    if not result.empty:
        result = result.sort_values(
            ["sharpe", "excess_return", "max_drawdown", "turnover"],
            ascending=[False, False, False, True],
        ).reset_index(drop=True)
    return write_parquet(result, root / "ads" / "parameter_sensitivity.parquet")
