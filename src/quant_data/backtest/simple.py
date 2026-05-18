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
    for column in ["is_suspended", "is_limit_up", "is_limit_down"]:
        if column not in result.columns:
            result[column] = False
    return result


def _tradability_snapshot(returns: pd.DataFrame, trade_date: pd.Timestamp) -> dict[str, dict[str, bool]]:
    day = returns[returns["trade_date"] == trade_date]
    return {
        row["symbol"]: {
            "is_suspended": bool(row["is_suspended"]),
            "is_limit_up": bool(row["is_limit_up"]),
            "is_limit_down": bool(row["is_limit_down"]),
        }
        for _, row in day.iterrows()
    }


def _apply_trade_constraints(
    current_positions: set[str],
    target_positions: set[str],
    tradability: dict[str, dict[str, bool]],
) -> set[str]:
    sell_symbols = current_positions - target_positions
    buy_symbols = target_positions - current_positions
    keep_symbols = current_positions & target_positions

    executable_sells = {
        symbol
        for symbol in sell_symbols
        if not tradability.get(symbol, {}).get("is_suspended", False)
        and not tradability.get(symbol, {}).get("is_limit_down", False)
    }
    executable_buys = {
        symbol
        for symbol in buy_symbols
        if not tradability.get(symbol, {}).get("is_suspended", False)
        and not tradability.get(symbol, {}).get("is_limit_up", False)
    }
    blocked_sells = sell_symbols - executable_sells
    return keep_symbols | blocked_sells | executable_buys


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


def _sentiment_by_date(market_sentiment: pd.DataFrame | None) -> dict[pd.Timestamp, float]:
    if market_sentiment is None or market_sentiment.empty:
        return {}
    required_columns = {"trade_date", "market_sentiment_score"}
    missing_columns = required_columns - set(market_sentiment.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing market sentiment columns: {missing}")
    frame = market_sentiment[["trade_date", "market_sentiment_score"]].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).astype("datetime64[ns]")
    return {
        pd.Timestamp(row["trade_date"]): float(row["market_sentiment_score"])
        for _, row in frame.dropna(subset=["market_sentiment_score"]).iterrows()
    }


def _target_exposure_for_signal(
    sentiment_scores: dict[pd.Timestamp, float],
    signal_date: pd.Timestamp,
    sentiment_threshold: float | None,
    weak_sentiment_exposure: float,
    normal_exposure: float,
) -> float:
    if sentiment_threshold is None or signal_date not in sentiment_scores:
        return normal_exposure
    if sentiment_scores[signal_date] < sentiment_threshold:
        return weak_sentiment_exposure
    return normal_exposure


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
    commission_rate: float = 0.0,
    slippage_rate: float = 0.0,
    stamp_tax_rate: float = 0.0,
    market_sentiment: pd.DataFrame | None = None,
    sentiment_threshold: float | None = None,
    weak_sentiment_exposure: float = 0.5,
    normal_exposure: float = 1.0,
) -> tuple[pd.DataFrame, dict[str, float]]:
    if rebalance_interval < 1:
        raise ValueError("rebalance_interval must be >= 1")
    if transaction_cost < 0:
        raise ValueError("transaction_cost must be >= 0")
    if commission_rate < 0 or slippage_rate < 0 or stamp_tax_rate < 0:
        raise ValueError("commission_rate, slippage_rate and stamp_tax_rate must be >= 0")
    if not 0 <= weak_sentiment_exposure <= 1 or not 0 <= normal_exposure <= 1:
        raise ValueError("weak_sentiment_exposure and normal_exposure must be in [0, 1]")
    if weak_sentiment_exposure > normal_exposure:
        raise ValueError("weak_sentiment_exposure must be less than or equal to normal_exposure")

    factor_frame = factors.copy()
    factor_frame["trade_date"] = pd.to_datetime(factor_frame["trade_date"]).astype("datetime64[ns]")
    returns = compute_daily_returns(daily_bars)
    trade_dates = sorted(returns["trade_date"].unique())
    factor_dates = sorted(factor_frame["trade_date"].unique())
    execution_dates = {
        pd.Timestamp(factor_date): pd.Timestamp(trade_dates[index + 1])
        for index, factor_date in enumerate(trade_dates[:-1])
        if pd.Timestamp(factor_date) in set(factor_dates[::rebalance_interval])
    }
    rebalance_dates = set(execution_dates.values())

    portfolio_value = 1.0
    benchmark_value = 1.0
    current_positions: set[str] = set()
    total_turnover = 0.0
    total_cost = 0.0
    target_exposure = normal_exposure
    sentiment_scores = _sentiment_by_date(market_sentiment)
    rows = []

    for index, trade_date in enumerate(trade_dates):
        timestamp = pd.Timestamp(trade_date)

        if timestamp in rebalance_dates:
            signal_date = next(signal for signal, execution in execution_dates.items() if execution == timestamp)
            snapshot = factor_frame[factor_frame["trade_date"] == signal_date]
            target_positions = set(select_top_symbols(snapshot, factor_name, top_quantile))
            # 情绪择时只使用信号日已经产生的市场情绪分数，仓位调整在下一交易日执行。
            target_exposure = _target_exposure_for_signal(
                sentiment_scores,
                signal_date,
                sentiment_threshold,
                weak_sentiment_exposure,
                normal_exposure,
            )
            tradability = _tradability_snapshot(returns, timestamp)
            new_positions = _apply_trade_constraints(current_positions, target_positions, tradability)

            # 调仓成本按权重变化粗略估算：第一次建仓不扣成本，后续换仓按 turnover 扣。
            if current_positions:
                old_weight = {symbol: 1 / len(current_positions) for symbol in current_positions}
                new_weight = {symbol: 1 / len(new_positions) for symbol in new_positions}
                all_symbols = set(old_weight) | set(new_weight)
                turnover = sum(abs(new_weight.get(symbol, 0.0) - old_weight.get(symbol, 0.0)) for symbol in all_symbols)
                sell_turnover = sum(max(old_weight.get(symbol, 0.0) - new_weight.get(symbol, 0.0), 0.0) for symbol in all_symbols)
                cost_rate = turnover * (transaction_cost + commission_rate + slippage_rate) + sell_turnover * stamp_tax_rate
                portfolio_value *= 1 - cost_rate
                total_turnover += turnover
                total_cost += cost_rate
            elif new_positions:
                turnover = 1.0
                cost_rate = turnover * (transaction_cost + commission_rate + slippage_rate)
                portfolio_value *= 1 - cost_rate
                total_turnover += turnover
                total_cost += cost_rate
            current_positions = new_positions

        raw_portfolio_return = 0.0 if index == 0 else _portfolio_return_for_date(returns, timestamp, current_positions)
        portfolio_return = raw_portfolio_return * target_exposure
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
                "positions_count": len(current_positions),
                "target_exposure": target_exposure,
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
        "total_cost": float(total_cost),
        "average_exposure": float(result["target_exposure"].mean()) if not result.empty else 0.0,
    }
    return result[
        [
            "trade_date",
            "portfolio_value",
            "benchmark_value",
            "daily_return",
            "benchmark_return",
            "drawdown",
            "positions_count",
            "target_exposure",
        ]
    ], metrics
