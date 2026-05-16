import math

import numpy as np
import pandas as pd


def select_top_symbols(
    snapshot: pd.DataFrame,
    factor_name: str,
    top_quantile: float = 0.1,
) -> list[str]:
    if factor_name not in snapshot.columns:
        raise ValueError(f"Missing factor column: {factor_name}")
    if not 0 < top_quantile <= 1:
        raise ValueError("top_quantile must be in (0, 1]")

    valid = snapshot.dropna(subset=[factor_name]).sort_values(
        [factor_name, "symbol"], ascending=[False, True]
    )
    count = max(1, math.ceil(len(valid) * top_quantile))
    return valid.head(count)["symbol"].tolist()


def compute_daily_returns(daily_bars: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"trade_date", "symbol", "close"}
    missing_columns = required_columns - set(daily_bars.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")

    result = daily_bars.copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"]).astype("datetime64[ns]")
    result = result.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    result["daily_symbol_return"] = result.groupby("symbol")["close"].pct_change()
    return result


def _portfolio_return_for_date(
    returns: pd.DataFrame,
    trade_date: pd.Timestamp,
    positions: set[str],
) -> float:
    if not positions:
        return 0.0
    day_returns = returns[
        (returns["trade_date"] == trade_date) & (returns["symbol"].isin(positions))
    ]["daily_symbol_return"].dropna()
    if day_returns.empty:
        return 0.0
    # 当前版本使用等权持仓，因此组合收益就是持仓股票当日收益的简单平均。
    return float(day_returns.mean())


def _benchmark_return_for_date(returns: pd.DataFrame, trade_date: pd.Timestamp) -> float:
    day_returns = returns[returns["trade_date"] == trade_date]["daily_symbol_return"].dropna()
    if day_returns.empty:
        return 0.0
    return float(day_returns.mean())


def _max_drawdown(values: pd.Series) -> pd.Series:
    running_max = values.cummax()
    return values / running_max - 1


def _annualized_return(total_return: float, periods: int) -> float:
    if periods <= 1:
        return 0.0
    return float((1 + total_return) ** (252 / (periods - 1)) - 1)


def _sharpe(daily_returns: pd.Series) -> float:
    clean = daily_returns.dropna()
    if len(clean) < 2 or clean.std(ddof=1) == 0:
        return 0.0
    return float(clean.mean() / clean.std(ddof=1) * np.sqrt(252))


def run_simple_backtest(
    factors: pd.DataFrame,
    daily_bars: pd.DataFrame,
    factor_name: str,
    top_quantile: float = 0.1,
    rebalance_interval: int = 20,
    transaction_cost: float = 0.001,
) -> tuple[pd.DataFrame, dict[str, float]]:
    if rebalance_interval < 1:
        raise ValueError("rebalance_interval must be >= 1")
    if transaction_cost < 0:
        raise ValueError("transaction_cost must be >= 0")

    factor_frame = factors.copy()
    factor_frame["trade_date"] = pd.to_datetime(factor_frame["trade_date"]).astype("datetime64[ns]")
    returns = compute_daily_returns(daily_bars)
    trade_dates = sorted(returns["trade_date"].unique())
    factor_dates = sorted(factor_frame["trade_date"].unique())
    rebalance_dates = set(factor_dates[::rebalance_interval])

    portfolio_value = 1.0
    benchmark_value = 1.0
    current_positions: set[str] = set()
    total_turnover = 0.0
    rows = []

    for index, trade_date in enumerate(trade_dates):
        timestamp = pd.Timestamp(trade_date)

        if timestamp in rebalance_dates:
            snapshot = factor_frame[factor_frame["trade_date"] == timestamp]
            new_positions = set(select_top_symbols(snapshot, factor_name, top_quantile))

            # 调仓成本按权重变化粗略估算：第一次建仓不扣成本，后续换仓按 turnover 扣。
            if current_positions:
                old_weight = {symbol: 1 / len(current_positions) for symbol in current_positions}
                new_weight = {symbol: 1 / len(new_positions) for symbol in new_positions}
                all_symbols = set(old_weight) | set(new_weight)
                turnover = sum(abs(new_weight.get(symbol, 0.0) - old_weight.get(symbol, 0.0)) for symbol in all_symbols)
                portfolio_value *= 1 - turnover * transaction_cost
                total_turnover += turnover
            current_positions = new_positions

        portfolio_return = 0.0 if index == 0 else _portfolio_return_for_date(returns, timestamp, current_positions)
        benchmark_return = 0.0 if index == 0 else _benchmark_return_for_date(returns, timestamp)

        # 净值从 1.0 开始，之后每天按组合收益滚动更新。
        if index > 0:
            portfolio_value *= 1 + portfolio_return
            benchmark_value *= 1 + benchmark_return

        rows.append(
            {
                "trade_date": timestamp,
                "portfolio_value": portfolio_value,
                "benchmark_value": benchmark_value,
                "daily_return": portfolio_return,
                "benchmark_return": benchmark_return,
            }
        )

    result = pd.DataFrame(rows)
    result["drawdown"] = _max_drawdown(result["portfolio_value"])

    total_return = float(result["portfolio_value"].iloc[-1] - 1) if not result.empty else 0.0
    metrics = {
        "total_return": total_return,
        "annualized_return": _annualized_return(total_return, len(result)),
        "max_drawdown": float(result["drawdown"].min()) if not result.empty else 0.0,
        "sharpe": _sharpe(result["daily_return"]),
        "turnover": float(total_turnover),
    }
    return result[
        [
            "trade_date",
            "portfolio_value",
            "benchmark_value",
            "daily_return",
            "benchmark_return",
            "drawdown",
        ]
    ], metrics
