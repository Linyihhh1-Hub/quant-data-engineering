import pandas as pd

from quant_data.backtest.simple import (
    compute_daily_returns,
    run_simple_backtest,
    select_top_symbols,
)


def make_backtest_daily_bars() -> pd.DataFrame:
    rows = []
    closes = {
        "000001.SZ": [10, 11, 12, 13, 14, 15],
        "000002.SZ": [20, 22, 24, 26, 28, 30],
        "600000.SH": [30, 29, 28, 27, 26, 25],
        "600001.SH": [40, 38, 36, 34, 32, 30],
    }
    for idx in range(6):
        day = pd.Timestamp("2024-01-01") + pd.Timedelta(days=idx)
        for symbol, values in closes.items():
            rows.append({"trade_date": day, "symbol": symbol, "close": float(values[idx])})
    return pd.DataFrame(rows).sample(frac=1, random_state=11).reset_index(drop=True)


def make_backtest_factors() -> pd.DataFrame:
    symbols = ["000001.SZ", "000002.SZ", "600000.SH", "600001.SH"]
    rows = []
    for idx in [0, 2, 4]:
        day = pd.Timestamp("2024-01-01") + pd.Timedelta(days=idx)
        for value, symbol in enumerate(symbols, start=1):
            rows.append({"trade_date": day, "symbol": symbol, "test_factor": float(value)})
    return pd.DataFrame(rows)


def test_select_top_symbols_selects_highest_factor_values():
    snapshot = make_backtest_factors()
    snapshot = snapshot[snapshot["trade_date"] == pd.Timestamp("2024-01-01")]

    result = select_top_symbols(snapshot, "test_factor", top_quantile=0.5)

    assert result == ["600001.SH", "600000.SH"]


def test_compute_daily_returns_calculates_per_symbol_returns():
    result = compute_daily_returns(make_backtest_daily_bars())
    pingan = result[result["symbol"] == "000001.SZ"].reset_index(drop=True)
    pudong = result[result["symbol"] == "600000.SH"].reset_index(drop=True)

    assert pd.isna(pingan.loc[0, "daily_symbol_return"])
    assert round(pingan.loc[1, "daily_symbol_return"], 6) == 0.1
    assert round(pudong.loc[1, "daily_symbol_return"], 6) == round(29 / 30 - 1, 6)


def test_run_simple_backtest_returns_daily_series_and_metrics():
    daily_result, metrics = run_simple_backtest(
        make_backtest_factors(),
        make_backtest_daily_bars(),
        "test_factor",
        top_quantile=0.5,
        rebalance_interval=1,
        transaction_cost=0.0,
    )

    assert daily_result.columns.tolist() == [
        "trade_date",
        "portfolio_value",
        "benchmark_value",
        "daily_return",
        "benchmark_return",
        "drawdown",
        "positions_count",
    ]
    assert daily_result.loc[0, "portfolio_value"] == 1.0
    assert daily_result.loc[0, "benchmark_value"] == 1.0
    assert {"total_return", "annualized_return", "max_drawdown", "sharpe", "turnover", "total_cost"} == set(metrics)


def test_run_simple_backtest_applies_selected_portfolio_returns():
    daily_result, metrics = run_simple_backtest(
        make_backtest_factors(),
        make_backtest_daily_bars(),
        "test_factor",
        top_quantile=0.5,
        rebalance_interval=1,
        transaction_cost=0.0,
    )

    expected_first_return = ((29 / 30 - 1) + (38 / 40 - 1)) / 2
    assert round(daily_result.loc[1, "daily_return"], 6) == round(expected_first_return, 6)
    assert metrics["max_drawdown"] <= 0
    assert metrics["turnover"] >= 0


def test_run_simple_backtest_executes_factor_signal_on_next_trade_day():
    daily = pd.DataFrame(
        [
            {"trade_date": "2024-01-01", "symbol": "000001.SZ", "close": 10.0},
            {"trade_date": "2024-01-02", "symbol": "000001.SZ", "close": 11.0},
            {"trade_date": "2024-01-03", "symbol": "000001.SZ", "close": 12.0},
        ]
    )
    factors = pd.DataFrame(
        [{"trade_date": "2024-01-01", "symbol": "000001.SZ", "test_factor": 1.0}]
    )

    result, _ = run_simple_backtest(
        factors,
        daily,
        "test_factor",
        top_quantile=1.0,
        rebalance_interval=1,
        transaction_cost=0.0,
    )

    assert result.loc[0, "positions_count"] == 0
    assert result.loc[1, "positions_count"] == 1


def test_run_simple_backtest_respects_limit_and_fee_constraints():
    daily = pd.DataFrame(
        [
            {"trade_date": "2024-01-01", "symbol": "AAA", "close": 10.0, "is_limit_up": False, "is_limit_down": False, "is_suspended": False},
            {"trade_date": "2024-01-01", "symbol": "BBB", "close": 10.0, "is_limit_up": False, "is_limit_down": False, "is_suspended": False},
            {"trade_date": "2024-01-02", "symbol": "AAA", "close": 11.0, "is_limit_up": True, "is_limit_down": False, "is_suspended": False},
            {"trade_date": "2024-01-02", "symbol": "BBB", "close": 9.0, "is_limit_up": False, "is_limit_down": True, "is_suspended": False},
            {"trade_date": "2024-01-03", "symbol": "AAA", "close": 12.0, "is_limit_up": False, "is_limit_down": False, "is_suspended": False},
            {"trade_date": "2024-01-03", "symbol": "BBB", "close": 8.0, "is_limit_up": False, "is_limit_down": False, "is_suspended": False},
        ]
    )
    factors = pd.DataFrame(
        [
            {"trade_date": "2024-01-01", "symbol": "AAA", "test_factor": 2.0},
            {"trade_date": "2024-01-01", "symbol": "BBB", "test_factor": 1.0},
            {"trade_date": "2024-01-02", "symbol": "AAA", "test_factor": 1.0},
            {"trade_date": "2024-01-02", "symbol": "BBB", "test_factor": 2.0},
        ]
    )

    result, metrics = run_simple_backtest(
        factors,
        daily,
        "test_factor",
        top_quantile=0.5,
        rebalance_interval=1,
        transaction_cost=0.0,
        commission_rate=0.001,
        slippage_rate=0.001,
        stamp_tax_rate=0.001,
    )

    assert result.loc[1, "positions_count"] == 0
    assert result.loc[2, "positions_count"] == 1
    assert metrics["total_cost"] > 0
