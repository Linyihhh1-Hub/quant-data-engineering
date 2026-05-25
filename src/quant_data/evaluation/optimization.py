import json
from pathlib import Path
from typing import Any

import pandas as pd

from quant_data.storage.parquet import write_parquet


REPORT_COLUMNS = [
    "rank",
    "source",
    "factor_name",
    "recommendation",
    "score",
    "factor_direction",
    "top_quantile",
    "rebalance_interval",
    "annualized_return",
    "total_return",
    "sharpe",
    "max_drawdown",
    "turnover",
    "total_cost",
    "cost_drag",
    "cost_to_return",
    "average_exposure",
    "cost_warning",
    "risk_warning",
    "suggested_action",
]


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_backtest_metrics(ads_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(ads_dir.glob("backtest_metrics_*.json")):
        metrics = json.loads(path.read_text(encoding="utf-8"))
        factor_name = path.stem.replace("backtest_metrics_", "")
        rows.append({"source": "backtest_metrics", "factor_name": factor_name, **metrics})
    return pd.DataFrame(rows)


def _load_parameter_sensitivity(ads_dir: Path) -> pd.DataFrame:
    path = ads_dir / "parameter_sensitivity.parquet"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["source"] = "parameter_sensitivity"
    return frame


def _normalize_candidates(backtest_metrics: pd.DataFrame, parameter_sensitivity: pd.DataFrame) -> pd.DataFrame:
    frames = [frame for frame in [backtest_metrics, parameter_sensitivity] if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=REPORT_COLUMNS)

    candidates = pd.concat(frames, ignore_index=True, sort=False)
    for column in [
        "annualized_return",
        "total_return",
        "sharpe",
        "max_drawdown",
        "turnover",
        "total_cost",
        "cost_drag",
        "cost_to_return",
        "average_exposure",
        "top_quantile",
        "rebalance_interval",
    ]:
        if column not in candidates.columns:
            candidates[column] = 0.0
        candidates[column] = candidates[column].map(_as_float)

    if "factor_direction" not in candidates.columns:
        candidates["factor_direction"] = ""
    candidates["factor_direction"] = candidates["factor_direction"].fillna("")
    return candidates


def _cost_warning(row: pd.Series) -> str:
    cost_to_return = _as_float(row.get("cost_to_return"))
    cost_drag = _as_float(row.get("cost_drag"))
    if cost_to_return >= 0.4 or cost_drag >= 0.15:
        return "high_cost_drag"
    if cost_to_return >= 0.2 or cost_drag >= 0.08:
        return "medium_cost_drag"
    return "ok"


def _risk_warning(row: pd.Series) -> str:
    max_drawdown = _as_float(row.get("max_drawdown"))
    sharpe = _as_float(row.get("sharpe"))
    turnover = _as_float(row.get("turnover"))
    if max_drawdown <= -0.35:
        return "deep_drawdown"
    if sharpe < 0.3:
        return "low_sharpe"
    if turnover >= 100:
        return "high_turnover"
    return "ok"


def _suggested_action(row: pd.Series) -> str:
    actions = []
    if row["cost_warning"] == "high_cost_drag" or _as_float(row.get("turnover")) >= 80:
        actions.append("increase rebalance interval")
    if row["risk_warning"] == "deep_drawdown":
        actions.append("reduce concentration or add risk filter")
    if row["risk_warning"] == "low_sharpe":
        actions.append("test opposite factor_direction")
    if not actions:
        actions.append("keep as candidate and validate by year")
    return "; ".join(actions)


def build_strategy_optimization_report(data_dir: str | Path) -> pd.DataFrame:
    root = Path(data_dir)
    ads_dir = root / "ads"
    candidates = _normalize_candidates(_load_backtest_metrics(ads_dir), _load_parameter_sensitivity(ads_dir))
    if candidates.empty:
        return pd.DataFrame(columns=REPORT_COLUMNS)

    candidates["cost_warning"] = candidates.apply(_cost_warning, axis=1)
    candidates["risk_warning"] = candidates.apply(_risk_warning, axis=1)
    candidates["score"] = (
        candidates["sharpe"] * 1.0
        + candidates["annualized_return"] * 0.8
        + candidates["total_return"] * 0.15
        + candidates["max_drawdown"] * 0.6
        - candidates["cost_to_return"].clip(lower=0) * 0.2
        - (candidates["turnover"].clip(lower=0) / 1000.0)
    )
    candidates = candidates.sort_values(
        ["score", "sharpe", "annualized_return", "max_drawdown", "turnover"],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)
    candidates["rank"] = candidates.index + 1
    candidates["recommendation"] = "watch"
    candidates.loc[candidates.index[:3], "recommendation"] = "prefer"
    candidates["suggested_action"] = candidates.apply(_suggested_action, axis=1)
    return candidates[REPORT_COLUMNS]


def write_strategy_optimization_report(data_dir: str | Path) -> Path:
    root = Path(data_dir)
    report = build_strategy_optimization_report(root)
    return write_parquet(report, root / "ads" / "strategy_optimization_report.parquet")
