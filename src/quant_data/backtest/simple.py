import math

import numpy as np
import pandas as pd


def select_top_symbols(
    snapshot: pd.DataFrame,
    factor_name: str,
    top_quantile: float = 0.1,
    factor_direction: str = "top",
) -> list[str]:
    if factor_name not in snapshot.columns:
        raise ValueError(f"Missing factor column: {factor_name}")
    if not 0 < top_quantile <= 1:
        raise ValueError("top_quantile must be in (0, 1]")
    if factor_direction not in {"top", "bottom"}:
        raise ValueError("factor_direction must be 'top' or 'bottom'")

    ascending = factor_direction == "bottom"
    valid = snapshot.dropna(subset=[factor_name]).sort_values(
        [factor_name, "symbol"], ascending=[ascending, True]
    )
    count = max(1, math.ceil(len(valid) * top_quantile))
    return valid.head(count)["symbol"].tolist()


def select_buffered_symbols(
    snapshot: pd.DataFrame,
    factor_name: str,
    current_positions: set[str],
    top_quantile: float = 0.1,
    entry_quantile: float | None = None,
    exit_quantile: float | None = None,
    factor_direction: str = "top",
) -> set[str]:
    entry = top_quantile if entry_quantile is None else entry_quantile
    exit_ = top_quantile if exit_quantile is None else exit_quantile
    for name, value in {"top_quantile": top_quantile, "entry_quantile": entry, "exit_quantile": exit_}.items():
        if not 0 < value <= 1:
            raise ValueError(f"{name} must be in (0, 1]")
    if entry > exit_:
        raise ValueError("entry_quantile must be less than or equal to exit_quantile")
    if factor_direction not in {"top", "bottom"}:
        raise ValueError("factor_direction must be 'top' or 'bottom'")

    if factor_name not in snapshot.columns:
        raise ValueError(f"Missing factor column: {factor_name}")
    ascending = factor_direction == "bottom"
    valid = snapshot.dropna(subset=[factor_name]).sort_values([factor_name, "symbol"], ascending=[ascending, True])
    target_count = max(1, math.ceil(len(valid) * top_quantile))
    entry_count = max(1, math.ceil(len(valid) * entry))
    exit_count = max(1, math.ceil(len(valid) * exit_))
    entry_symbols = valid.head(entry_count)["symbol"].tolist()
    hold_universe = set(valid.head(exit_count)["symbol"].tolist())
    kept = [symbol for symbol in entry_symbols if symbol in current_positions and symbol in hold_universe]
    kept.extend(sorted(symbol for symbol in current_positions if symbol in hold_universe and symbol not in kept))
    selected = kept[:target_count]
    for symbol in entry_symbols:
        if len(selected) >= target_count:
            break
        if symbol not in selected:
            selected.append(symbol)
    return set(selected)


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


def _tradability_filters_for_date(daily_bars: pd.DataFrame, signal_date: pd.Timestamp) -> pd.DataFrame:
    available_columns = [
        column
        for column in ["trade_date", "symbol", "amount", "volume", "is_st"]
        if column in daily_bars.columns
    ]
    if not {"trade_date", "symbol"}.issubset(available_columns):
        return pd.DataFrame({"symbol": []})
    frame = daily_bars[available_columns].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).astype("datetime64[ns]")
    return frame[frame["trade_date"] == signal_date].drop_duplicates(subset=["symbol"], keep="last")


def _apply_universe_filters(
    snapshot: pd.DataFrame,
    daily_bars: pd.DataFrame,
    signal_date: pd.Timestamp,
    min_amount: float | None,
    min_volume: float | None,
    exclude_st: bool,
) -> pd.DataFrame:
    if snapshot.empty:
        return snapshot
    filters = _tradability_filters_for_date(daily_bars, signal_date)
    if filters.empty:
        return snapshot
    result = snapshot.merge(filters.drop(columns=["trade_date"], errors="ignore"), on="symbol", how="left")
    if min_amount is not None and "amount" in result.columns:
        result = result[result["amount"].fillna(0) >= min_amount]
    if min_volume is not None and "volume" in result.columns:
        result = result[result["volume"].fillna(0) >= min_volume]
    if exclude_st and "is_st" in result.columns:
        result = result[result["is_st"] != True]  # noqa: E712 - preserve pandas nullable bool semantics.
    return result


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


def _index_return_by_date(index_bars: pd.DataFrame | None) -> dict[pd.Timestamp, float]:
    if index_bars is None or index_bars.empty:
        return {}
    required_columns = {"trade_date", "close"}
    missing_columns = required_columns - set(index_bars.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing index columns: {missing}")
    frame = index_bars[["trade_date", "close"]].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).astype("datetime64[ns]")
    frame = frame.sort_values("trade_date").reset_index(drop=True)
    frame["index_return"] = frame["close"].pct_change()
    return {
        pd.Timestamp(row["trade_date"]): float(row["index_return"])
        for _, row in frame.dropna(subset=["index_return"]).iterrows()
    }


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


def _raw_target_exposure(
    sentiment_scores: dict[pd.Timestamp, float],
    signal_date: pd.Timestamp,
    sentiment_threshold: float | None,
    weak_sentiment_exposure: float,
    normal_exposure: float,
    sentiment_mode: str,
    min_exposure: float,
    max_exposure: float,
    base_exposure: float,
    sentiment_scale: float,
) -> tuple[float, float | None]:
    score = sentiment_scores.get(signal_date)
    if sentiment_mode == "step":
        return (
            _target_exposure_for_signal(sentiment_scores, signal_date, sentiment_threshold, weak_sentiment_exposure, normal_exposure),
            score,
        )
    if score is None:
        return normal_exposure, None
    raw = base_exposure + sentiment_scale * score
    return float(np.clip(raw, min_exposure, max_exposure)), score


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
    factor_direction: str = "top",
    entry_quantile: float | None = None,
    exit_quantile: float | None = None,
    transaction_cost: float = 0.001,
    commission_rate: float = 0.0,
    slippage_rate: float = 0.0,
    stamp_tax_rate: float = 0.0,
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
) -> tuple[pd.DataFrame, dict[str, float]]:
    if rebalance_interval < 1:
        raise ValueError("rebalance_interval must be >= 1")
    if transaction_cost < 0:
        raise ValueError("transaction_cost must be >= 0")
    if factor_direction not in {"top", "bottom"}:
        raise ValueError("factor_direction must be 'top' or 'bottom'")
    if sentiment_mode not in {"step", "smooth"}:
        raise ValueError("sentiment_mode must be 'step' or 'smooth'")
    if not 0 < sentiment_smooth_alpha <= 1:
        raise ValueError("sentiment_smooth_alpha must be in (0, 1]")
    if commission_rate < 0 or slippage_rate < 0 or stamp_tax_rate < 0:
        raise ValueError("commission_rate, slippage_rate and stamp_tax_rate must be >= 0")
    if not 0 <= weak_sentiment_exposure <= 1 or not 0 <= normal_exposure <= 1:
        raise ValueError("weak_sentiment_exposure and normal_exposure must be in [0, 1]")
    if not 0 <= min_exposure <= max_exposure <= 1:
        raise ValueError("min_exposure and max_exposure must satisfy 0 <= min <= max <= 1")
    if weak_sentiment_exposure > normal_exposure:
        raise ValueError("weak_sentiment_exposure must be less than or equal to normal_exposure")
    if min_amount is not None and min_amount < 0:
        raise ValueError("min_amount must be >= 0")
    if min_volume is not None and min_volume < 0:
        raise ValueError("min_volume must be >= 0")

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
    gross_portfolio_value = 1.0
    benchmark_value = 1.0
    hs300_benchmark_value = 1.0
    current_positions: set[str] = set()
    total_turnover = 0.0
    total_cost = 0.0
    target_exposure = normal_exposure
    raw_target_exposure = normal_exposure
    market_sentiment_score = None
    rebalance_count = 0
    sentiment_scores = _sentiment_by_date(market_sentiment)
    index_returns = _index_return_by_date(benchmark_index)
    rows = []

    for index, trade_date in enumerate(trade_dates):
        timestamp = pd.Timestamp(trade_date)
        daily_turnover = 0.0
        daily_cost_rate = 0.0

        if timestamp in rebalance_dates:
            signal_date = next(signal for signal, execution in execution_dates.items() if execution == timestamp)
            snapshot = factor_frame[factor_frame["trade_date"] == signal_date]
            snapshot = _apply_universe_filters(
                snapshot,
                daily_bars,
                signal_date,
                min_amount=min_amount,
                min_volume=min_volume,
                exclude_st=exclude_st,
            )
            target_positions = select_buffered_symbols(
                snapshot,
                factor_name,
                current_positions,
                top_quantile=top_quantile,
                entry_quantile=entry_quantile,
                exit_quantile=exit_quantile,
                factor_direction=factor_direction,
            )
            # 情绪择时只使用信号日已经产生的市场情绪分数，仓位调整在下一交易日执行。
            raw_target_exposure, market_sentiment_score = _raw_target_exposure(
                sentiment_scores,
                signal_date,
                sentiment_threshold,
                weak_sentiment_exposure,
                normal_exposure,
                sentiment_mode,
                min_exposure,
                max_exposure,
                base_exposure,
                sentiment_scale,
            )
            if sentiment_mode == "smooth":
                target_exposure = (
                    sentiment_smooth_alpha * raw_target_exposure
                    + (1 - sentiment_smooth_alpha) * target_exposure
                )
            else:
                target_exposure = raw_target_exposure
            tradability = _tradability_snapshot(returns, timestamp)
            new_positions = _apply_trade_constraints(current_positions, target_positions, tradability)
            rebalance_count += 1

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
                daily_turnover = turnover
                daily_cost_rate = cost_rate
            elif new_positions:
                turnover = 1.0
                cost_rate = turnover * (transaction_cost + commission_rate + slippage_rate)
                portfolio_value *= 1 - cost_rate
                total_turnover += turnover
                total_cost += cost_rate
                daily_turnover = turnover
                daily_cost_rate = cost_rate
            current_positions = new_positions

        raw_portfolio_return = 0.0 if index == 0 else _portfolio_return_for_date(returns, timestamp, current_positions)
        portfolio_return = raw_portfolio_return * target_exposure
        benchmark_return = 0.0 if index == 0 else _benchmark_return_for_date(returns, timestamp)
        hs300_benchmark_return = 0.0 if index == 0 else index_returns.get(timestamp, 0.0)

        # 净值从 1.0 开始，之后每天按组合收益滚动更新。
        if index > 0:
            gross_portfolio_value *= 1 + portfolio_return
            portfolio_value *= 1 + portfolio_return
            benchmark_value *= 1 + benchmark_return
            hs300_benchmark_value *= 1 + hs300_benchmark_return

        rows.append(
            {
                "trade_date": timestamp,
                "gross_portfolio_value": gross_portfolio_value,
                "portfolio_value": portfolio_value,
                "benchmark_value": benchmark_value,
                "hs300_benchmark_value": hs300_benchmark_value,
                "daily_return": portfolio_return,
                "benchmark_return": benchmark_return,
                "hs300_benchmark_return": hs300_benchmark_return,
                "positions_count": len(current_positions),
                "factor_direction": factor_direction,
                "market_sentiment_score": market_sentiment_score,
                "raw_target_exposure": raw_target_exposure,
                "target_exposure": target_exposure,
                "sentiment_mode": sentiment_mode,
                "daily_turnover": daily_turnover,
                "daily_cost_rate": daily_cost_rate,
            }
        )

    result = pd.DataFrame(rows)
    result["drawdown"] = _max_drawdown(result["portfolio_value"])
    exposure_turnover = float(result["target_exposure"].diff().abs().fillna(0).sum()) if not result.empty else 0.0

    total_return = float(result["portfolio_value"].iloc[-1] - 1) if not result.empty else 0.0
    gross_total_return = float(result["gross_portfolio_value"].iloc[-1] - 1) if not result.empty else 0.0
    net_daily_return = result["portfolio_value"].pct_change().fillna(0.0) if not result.empty else pd.Series(dtype="float64")
    metrics = {
        "total_return": total_return,
        "gross_total_return": gross_total_return,
        "cost_drag": gross_total_return - total_return,
        "cost_return_ratio": float(total_cost / abs(gross_total_return)) if gross_total_return != 0 else 0.0,
        "cost_to_return": float(total_cost / abs(gross_total_return)) if gross_total_return != 0 else 0.0,
        "annualized_return": _annualized_return(total_return, len(result)),
        "equal_weight_total_return": float(result["benchmark_value"].iloc[-1] - 1) if not result.empty else 0.0,
        "hs300_total_return": float(result["hs300_benchmark_value"].iloc[-1] - 1) if not result.empty else 0.0,
        "hs300_excess_return": total_return - float(result["hs300_benchmark_value"].iloc[-1] - 1)
        if not result.empty
        else 0.0,
        "max_drawdown": float(result["drawdown"].min()) if not result.empty else 0.0,
        "sharpe": _sharpe(net_daily_return),
        "turnover": float(total_turnover),
        "total_cost": float(total_cost),
        "factor_direction": factor_direction,
        "top_quantile": float(top_quantile),
        "rebalance_interval": float(rebalance_interval),
        "entry_quantile": float(top_quantile if entry_quantile is None else entry_quantile),
        "exit_quantile": float(top_quantile if exit_quantile is None else exit_quantile),
        "average_holding_count": float(result["positions_count"].mean()) if not result.empty else 0.0,
        "rebalance_count": float(rebalance_count),
        "average_turnover_per_rebalance": float(total_turnover / rebalance_count) if rebalance_count else 0.0,
        "sentiment_mode": sentiment_mode,
        "min_exposure": float(min_exposure),
        "max_exposure": float(max_exposure),
        "base_exposure": float(base_exposure),
        "sentiment_scale": float(sentiment_scale),
        "sentiment_smooth_alpha": float(sentiment_smooth_alpha),
        "average_exposure": float(result["target_exposure"].mean()) if not result.empty else 0.0,
        "exposure_turnover": exposure_turnover,
        "min_amount": float(min_amount or 0.0),
        "min_volume": float(min_volume or 0.0),
        "exclude_st": float(bool(exclude_st)),
    }
    return result[
        [
            "trade_date",
            "gross_portfolio_value",
            "portfolio_value",
            "benchmark_value",
            "hs300_benchmark_value",
            "daily_return",
            "benchmark_return",
            "hs300_benchmark_return",
            "drawdown",
            "positions_count",
            "factor_direction",
            "market_sentiment_score",
            "raw_target_exposure",
            "target_exposure",
            "sentiment_mode",
            "daily_turnover",
            "daily_cost_rate",
        ]
    ], metrics
