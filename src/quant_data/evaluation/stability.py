import json
from pathlib import Path

import numpy as np
import pandas as pd

from quant_data.storage.parquet import read_parquet, write_parquet


def _read_json_if_exists(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _sharpe(daily_returns: pd.Series) -> float:
    clean = daily_returns.dropna()
    if len(clean) < 2 or clean.std(ddof=1) == 0:
        return 0.0
    return float(clean.mean() / clean.std(ddof=1) * np.sqrt(252))


def _icir(values: pd.Series) -> float:
    clean = values.dropna()
    if len(clean) < 2 or clean.std(ddof=1) == 0:
        return 0.0
    return float(clean.mean() / clean.std(ddof=1))


def _period_return(values: pd.Series) -> float:
    clean = values.dropna()
    if len(clean) < 2 or clean.iloc[0] == 0:
        return 0.0
    return float(clean.iloc[-1] / clean.iloc[0] - 1)


def _max_drawdown(values: pd.Series) -> float:
    clean = values.dropna()
    if clean.empty:
        return 0.0
    drawdown = clean / clean.cummax() - 1
    return float(drawdown.min())


def summarize_factor_yearly(
    evaluation: pd.DataFrame,
    backtest_daily: pd.DataFrame,
    metrics: dict[str, float] | None = None,
) -> pd.DataFrame:
    if evaluation.empty or "factor_name" not in evaluation.columns:
        return pd.DataFrame()

    eval_frame = evaluation.copy()
    eval_frame["trade_date"] = pd.to_datetime(eval_frame["trade_date"]).astype("datetime64[ns]")
    eval_frame["year"] = eval_frame["trade_date"].dt.year

    bt_frame = backtest_daily.copy()
    if not bt_frame.empty and "trade_date" in bt_frame.columns:
        bt_frame["trade_date"] = pd.to_datetime(bt_frame["trade_date"]).astype("datetime64[ns]")
        bt_frame["year"] = bt_frame["trade_date"].dt.year

    rows = []
    factor_names = sorted(eval_frame["factor_name"].dropna().unique())
    for factor_name in factor_names:
        factor_eval = eval_frame[eval_frame["factor_name"] == factor_name]
        for year, group in factor_eval.groupby("year"):
            ic = group["ic"].dropna() if "ic" in group.columns else pd.Series(dtype="float64")
            rank_ic = group["rank_ic"].dropna() if "rank_ic" in group.columns else pd.Series(dtype="float64")
            daily = bt_frame[bt_frame["year"] == year] if "year" in bt_frame.columns else pd.DataFrame()
            total_return = _period_return(daily["portfolio_value"]) if "portfolio_value" in daily.columns else 0.0
            benchmark_return = _period_return(daily["benchmark_value"]) if "benchmark_value" in daily.columns else 0.0
            row = {
                "year": int(year),
                "factor_name": factor_name,
                "ic_mean": float(ic.mean()) if not ic.empty else 0.0,
                "rank_ic_mean": float(rank_ic.mean()) if not rank_ic.empty else 0.0,
                "positive_ic_ratio": float((ic > 0).mean()) if not ic.empty else 0.0,
                "icir": _icir(ic),
                "total_return": total_return,
                "benchmark_total_return": benchmark_return,
                "excess_return": total_return - benchmark_return,
                "max_drawdown": _max_drawdown(daily["portfolio_value"]) if "portfolio_value" in daily.columns else 0.0,
                "sharpe": _sharpe(daily["daily_return"]) if "daily_return" in daily.columns else 0.0,
                "turnover": float(daily["daily_turnover"].fillna(0).sum()) if "daily_turnover" in daily.columns else 0.0,
            }
            if metrics:
                row["full_period_turnover"] = float(metrics.get("turnover", 0.0))
            rows.append(row)

    return pd.DataFrame(rows).sort_values(["factor_name", "year"]).reset_index(drop=True)


def _rolling_max_drawdown(values: pd.Series) -> float:
    if len(values) == 0:
        return 0.0
    clean = pd.Series(values).dropna()
    if clean.empty:
        return 0.0
    return _max_drawdown(clean)


def summarize_factor_rolling(
    evaluation: pd.DataFrame,
    backtest_daily: pd.DataFrame,
    rank_ic_window: int = 60,
    return_window: int = 120,
) -> pd.DataFrame:
    if evaluation.empty or "factor_name" not in evaluation.columns:
        return pd.DataFrame()

    eval_frame = evaluation.copy()
    eval_frame["trade_date"] = pd.to_datetime(eval_frame["trade_date"]).astype("datetime64[ns]")
    eval_frame = eval_frame.sort_values(["factor_name", "trade_date"]).reset_index(drop=True)
    eval_frame["rolling_60d_rank_ic_mean"] = eval_frame.groupby("factor_name")["rank_ic"].transform(
        lambda series: series.rolling(rank_ic_window, min_periods=max(2, rank_ic_window // 3)).mean()
    )

    bt_frame = backtest_daily.copy()
    if not bt_frame.empty and "trade_date" in bt_frame.columns:
        bt_frame["trade_date"] = pd.to_datetime(bt_frame["trade_date"]).astype("datetime64[ns]")
        bt_frame = bt_frame.sort_values("trade_date").reset_index(drop=True)
        if {"portfolio_value", "benchmark_value"}.issubset(bt_frame.columns):
            portfolio_return = bt_frame["portfolio_value"] / bt_frame["portfolio_value"].shift(return_window) - 1
            benchmark_return = bt_frame["benchmark_value"] / bt_frame["benchmark_value"].shift(return_window) - 1
            bt_frame["rolling_120d_excess_return"] = portfolio_return - benchmark_return
            bt_frame["rolling_120d_max_drawdown"] = bt_frame["portfolio_value"].rolling(
                return_window, min_periods=max(2, return_window // 3)
            ).apply(_rolling_max_drawdown, raw=False)
        bt_frame = bt_frame[["trade_date", "rolling_120d_excess_return", "rolling_120d_max_drawdown"]]
    else:
        bt_frame = pd.DataFrame(columns=["trade_date", "rolling_120d_excess_return", "rolling_120d_max_drawdown"])

    result = eval_frame[["trade_date", "factor_name", "rolling_60d_rank_ic_mean"]].merge(
        bt_frame, on="trade_date", how="left"
    )
    return result.sort_values(["factor_name", "trade_date"]).reset_index(drop=True)


def write_stability_reports(
    data_dir: str | Path,
    factor_names: list[str],
    rank_ic_window: int = 60,
    return_window: int = 120,
) -> tuple[Path, Path]:
    root = Path(data_dir)
    yearly_frames = []
    rolling_frames = []

    for factor_name in factor_names:
        evaluation_path = root / "ads" / f"factor_eval_{factor_name}.parquet"
        backtest_path = root / "ads" / f"backtest_daily_{factor_name}.parquet"
        metrics_path = root / "ads" / f"backtest_metrics_{factor_name}.json"
        if not evaluation_path.exists() or not backtest_path.exists():
            continue
        evaluation = read_parquet(evaluation_path)
        backtest_daily = read_parquet(backtest_path)
        metrics = _read_json_if_exists(metrics_path)
        yearly_frames.append(summarize_factor_yearly(evaluation, backtest_daily, metrics))
        rolling_frames.append(summarize_factor_rolling(evaluation, backtest_daily, rank_ic_window, return_window))

    yearly = pd.concat(yearly_frames, ignore_index=True) if yearly_frames else pd.DataFrame()
    rolling = pd.concat(rolling_frames, ignore_index=True) if rolling_frames else pd.DataFrame()
    yearly_path = write_parquet(yearly, root / "ads" / "factor_yearly_summary.parquet")
    rolling_path = write_parquet(rolling, root / "ads" / "factor_rolling_summary.parquet")
    return yearly_path, rolling_path
