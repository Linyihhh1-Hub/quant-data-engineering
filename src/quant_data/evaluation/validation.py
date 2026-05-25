from pathlib import Path
from typing import Any

import pandas as pd

from quant_data.backtest.simple import run_simple_backtest
from quant_data.storage.parquet import read_parquet, write_parquet


SUMMARY_COLUMNS = [
    "source_rank",
    "factor_name",
    "factor_direction",
    "top_quantile",
    "rebalance_interval",
    "train_period_start",
    "train_period_end",
    "validation_period_start",
    "validation_period_end",
    "train_total_return",
    "train_annualized_return",
    "train_sharpe",
    "train_max_drawdown",
    "train_turnover",
    "validation_total_return",
    "validation_annualized_return",
    "validation_sharpe",
    "validation_max_drawdown",
    "validation_turnover",
    "validation_cost_drag",
    "validation_cost_to_return",
    "min_amount",
    "min_volume",
    "exclude_st",
    "validation_status",
    "validation_notes",
]

YEARLY_COLUMNS = [
    "source_rank",
    "factor_name",
    "factor_direction",
    "top_quantile",
    "rebalance_interval",
    "year",
    "total_return",
    "annualized_return",
    "sharpe",
    "max_drawdown",
    "turnover",
    "cost_drag",
    "cost_to_return",
    "min_amount",
    "min_volume",
    "exclude_st",
]


def _parse_date(value: str | pd.Timestamp) -> pd.Timestamp:
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return pd.to_datetime(text, format="%Y%m%d")
    return pd.Timestamp(value)


def _as_float(value: Any, default: float) -> float:
    if value is None or pd.isna(value):
        return default
    return float(value)


def _load_optional_parquet(path: Path) -> pd.DataFrame | None:
    return read_parquet(path) if path.exists() else None


def _date_bounds(frame: pd.DataFrame) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    if frame.empty:
        return None, None
    dates = pd.to_datetime(frame["trade_date"])
    return pd.Timestamp(dates.min()), pd.Timestamp(dates.max())


def _run_candidate(
    factors: pd.DataFrame,
    daily_bars: pd.DataFrame,
    candidate: pd.Series,
    transaction_cost: float,
    commission_rate: float,
    slippage_rate: float,
    stamp_tax_rate: float,
    market_sentiment: pd.DataFrame | None,
    benchmark_index: pd.DataFrame | None,
    min_amount: float | None,
    min_volume: float | None,
    exclude_st: bool,
) -> dict[str, float]:
    factor_name = str(candidate["factor_name"])
    if factors.empty or daily_bars.empty or factor_name not in factors.columns:
        return {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "turnover": 0.0,
            "cost_drag": 0.0,
            "cost_to_return": 0.0,
        }
    _, metrics = run_simple_backtest(
        factors,
        daily_bars,
        factor_name,
        top_quantile=_as_float(candidate.get("top_quantile"), 0.1),
        rebalance_interval=int(_as_float(candidate.get("rebalance_interval"), 20)),
        factor_direction=str(candidate.get("factor_direction") or "top"),
        transaction_cost=transaction_cost,
        commission_rate=commission_rate,
        slippage_rate=slippage_rate,
        stamp_tax_rate=stamp_tax_rate,
        market_sentiment=market_sentiment,
        benchmark_index=benchmark_index,
        min_amount=min_amount,
        min_volume=min_volume,
        exclude_st=exclude_st,
    )
    return metrics


def _status(validation_metrics: dict[str, float]) -> tuple[str, str]:
    notes = []
    if validation_metrics["sharpe"] <= 0:
        notes.append("non_positive_validation_sharpe")
    if validation_metrics["max_drawdown"] <= -0.35:
        notes.append("deep_validation_drawdown")
    if validation_metrics["turnover"] >= 100:
        notes.append("high_validation_turnover")
    if validation_metrics["cost_to_return"] >= 0.4 or validation_metrics["cost_drag"] >= 0.15:
        notes.append("high_validation_cost_drag")
    if not notes:
        return "pass", "validation metrics are acceptable"
    if validation_metrics["sharpe"] > 0 and validation_metrics["max_drawdown"] > -0.35:
        return "watch", "; ".join(notes)
    return "reject", "; ".join(notes)


def build_candidate_validation_reports(
    data_dir: str | Path,
    top_n: int = 5,
    validation_start: str | pd.Timestamp = "20230101",
    transaction_cost: float = 0.001,
    commission_rate: float = 0.0003,
    slippage_rate: float = 0.0005,
    stamp_tax_rate: float = 0.0005,
    min_amount: float | None = None,
    min_volume: float | None = None,
    exclude_st: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root = Path(data_dir)
    ads_dir = root / "ads"
    candidates_path = ads_dir / "strategy_optimization_report.parquet"
    if not candidates_path.exists():
        raise FileNotFoundError(f"Missing strategy optimization report: {candidates_path}")

    candidates = read_parquet(candidates_path).head(top_n)
    factors = read_parquet(ads_dir / "factor_wide_daily.parquet").copy()
    daily_bars = read_parquet(root / "dwd" / "stock_daily.parquet").copy()
    market_sentiment = _load_optional_parquet(ads_dir / "market_sentiment_daily.parquet")
    benchmark_index = _load_optional_parquet(root / "dim" / "hs300_index.parquet")

    factors["trade_date"] = pd.to_datetime(factors["trade_date"]).astype("datetime64[ns]")
    daily_bars["trade_date"] = pd.to_datetime(daily_bars["trade_date"]).astype("datetime64[ns]")
    if market_sentiment is not None:
        market_sentiment["trade_date"] = pd.to_datetime(market_sentiment["trade_date"]).astype("datetime64[ns]")
    if benchmark_index is not None:
        benchmark_index["trade_date"] = pd.to_datetime(benchmark_index["trade_date"]).astype("datetime64[ns]")

    split = _parse_date(validation_start)
    summary_rows = []
    yearly_rows = []
    for _, candidate in candidates.iterrows():
        train_factors = factors[factors["trade_date"] < split]
        train_daily = daily_bars[daily_bars["trade_date"] < split]
        validation_factors = factors[factors["trade_date"] >= split]
        validation_daily = daily_bars[daily_bars["trade_date"] >= split]
        train_sentiment = market_sentiment[market_sentiment["trade_date"] < split] if market_sentiment is not None else None
        validation_sentiment = (
            market_sentiment[market_sentiment["trade_date"] >= split] if market_sentiment is not None else None
        )
        train_index = benchmark_index[benchmark_index["trade_date"] < split] if benchmark_index is not None else None
        validation_index = benchmark_index[benchmark_index["trade_date"] >= split] if benchmark_index is not None else None

        train_metrics = _run_candidate(
            train_factors,
            train_daily,
            candidate,
            transaction_cost,
            commission_rate,
            slippage_rate,
            stamp_tax_rate,
            train_sentiment,
            train_index,
            min_amount,
            min_volume,
            exclude_st,
        )
        validation_metrics = _run_candidate(
            validation_factors,
            validation_daily,
            candidate,
            transaction_cost,
            commission_rate,
            slippage_rate,
            stamp_tax_rate,
            validation_sentiment,
            validation_index,
            min_amount,
            min_volume,
            exclude_st,
        )
        validation_status, validation_notes = _status(validation_metrics)
        train_start, train_end = _date_bounds(train_daily)
        validation_start_date, validation_end = _date_bounds(validation_daily)
        summary_rows.append(
            {
                "source_rank": int(candidate["rank"]),
                "factor_name": candidate["factor_name"],
                "factor_direction": candidate.get("factor_direction") or "top",
                "top_quantile": _as_float(candidate.get("top_quantile"), 0.1),
                "rebalance_interval": int(_as_float(candidate.get("rebalance_interval"), 20)),
                "train_period_start": train_start,
                "train_period_end": train_end,
                "validation_period_start": validation_start_date,
                "validation_period_end": validation_end,
                "train_total_return": train_metrics["total_return"],
                "train_annualized_return": train_metrics["annualized_return"],
                "train_sharpe": train_metrics["sharpe"],
                "train_max_drawdown": train_metrics["max_drawdown"],
                "train_turnover": train_metrics["turnover"],
                "validation_total_return": validation_metrics["total_return"],
                "validation_annualized_return": validation_metrics["annualized_return"],
                "validation_sharpe": validation_metrics["sharpe"],
                "validation_max_drawdown": validation_metrics["max_drawdown"],
                "validation_turnover": validation_metrics["turnover"],
                "validation_cost_drag": validation_metrics["cost_drag"],
                "validation_cost_to_return": validation_metrics["cost_to_return"],
                "min_amount": float(min_amount or 0.0),
                "min_volume": float(min_volume or 0.0),
                "exclude_st": float(bool(exclude_st)),
                "validation_status": validation_status,
                "validation_notes": validation_notes,
            }
        )

        for year in sorted(daily_bars["trade_date"].dt.year.unique()):
            year_factors = factors[factors["trade_date"].dt.year == year]
            year_daily = daily_bars[daily_bars["trade_date"].dt.year == year]
            year_sentiment = market_sentiment[market_sentiment["trade_date"].dt.year == year] if market_sentiment is not None else None
            year_index = benchmark_index[benchmark_index["trade_date"].dt.year == year] if benchmark_index is not None else None
            year_metrics = _run_candidate(
                year_factors,
                year_daily,
                candidate,
                transaction_cost,
                commission_rate,
                slippage_rate,
                stamp_tax_rate,
                year_sentiment,
                year_index,
                min_amount,
                min_volume,
                exclude_st,
            )
            yearly_rows.append(
                {
                    "source_rank": int(candidate["rank"]),
                    "factor_name": candidate["factor_name"],
                    "factor_direction": candidate.get("factor_direction") or "top",
                    "top_quantile": _as_float(candidate.get("top_quantile"), 0.1),
                    "rebalance_interval": int(_as_float(candidate.get("rebalance_interval"), 20)),
                    "year": int(year),
                    "total_return": year_metrics["total_return"],
                    "annualized_return": year_metrics["annualized_return"],
                    "sharpe": year_metrics["sharpe"],
                    "max_drawdown": year_metrics["max_drawdown"],
                    "turnover": year_metrics["turnover"],
                    "cost_drag": year_metrics["cost_drag"],
                    "cost_to_return": year_metrics["cost_to_return"],
                    "min_amount": float(min_amount or 0.0),
                    "min_volume": float(min_volume or 0.0),
                    "exclude_st": float(bool(exclude_st)),
                }
            )

    return pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS), pd.DataFrame(yearly_rows, columns=YEARLY_COLUMNS)


def write_candidate_validation_reports(
    data_dir: str | Path,
    top_n: int = 5,
    validation_start: str | pd.Timestamp = "20230101",
    transaction_cost: float = 0.001,
    commission_rate: float = 0.0003,
    slippage_rate: float = 0.0005,
    stamp_tax_rate: float = 0.0005,
    min_amount: float | None = None,
    min_volume: float | None = None,
    exclude_st: bool = False,
) -> tuple[Path, Path]:
    root = Path(data_dir)
    summary, yearly = build_candidate_validation_reports(
        root,
        top_n=top_n,
        validation_start=validation_start,
        transaction_cost=transaction_cost,
        commission_rate=commission_rate,
        slippage_rate=slippage_rate,
        stamp_tax_rate=stamp_tax_rate,
        min_amount=min_amount,
        min_volume=min_volume,
        exclude_st=exclude_st,
    )
    return (
        write_parquet(summary, root / "ads" / "candidate_validation_report.parquet"),
        write_parquet(yearly, root / "ads" / "candidate_yearly_validation.parquet"),
    )
