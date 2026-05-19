import pandas as pd

from quant_data.evaluation.stability import summarize_factor_rolling
from quant_data.evaluation.stability import summarize_factor_yearly


def make_evaluation_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_date": pd.Timestamp("2023-12-29"),
                "factor_name": "momentum_20d",
                "ic": 0.10,
                "rank_ic": 0.20,
                "top_group_return": 0.03,
                "bottom_group_return": 0.01,
                "long_short_return": 0.02,
            },
            {
                "trade_date": pd.Timestamp("2024-01-02"),
                "factor_name": "momentum_20d",
                "ic": -0.02,
                "rank_ic": 0.05,
                "top_group_return": 0.01,
                "bottom_group_return": 0.02,
                "long_short_return": -0.01,
            },
            {
                "trade_date": pd.Timestamp("2024-01-03"),
                "factor_name": "momentum_20d",
                "ic": 0.04,
                "rank_ic": 0.07,
                "top_group_return": 0.02,
                "bottom_group_return": 0.01,
                "long_short_return": 0.01,
            },
        ]
    )


def make_backtest_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_date": pd.Timestamp("2023-12-29"),
                "portfolio_value": 1.00,
                "benchmark_value": 1.00,
                "daily_return": 0.00,
                "daily_turnover": 1.0,
            },
            {
                "trade_date": pd.Timestamp("2024-01-02"),
                "portfolio_value": 1.10,
                "benchmark_value": 1.05,
                "daily_return": 0.10,
                "daily_turnover": 0.5,
            },
            {
                "trade_date": pd.Timestamp("2024-01-03"),
                "portfolio_value": 1.05,
                "benchmark_value": 1.02,
                "daily_return": -0.045,
                "daily_turnover": 0.2,
            },
        ]
    )


def test_summarize_factor_yearly_combines_ic_and_backtest_metrics():
    result = summarize_factor_yearly(make_evaluation_frame(), make_backtest_frame(), {"turnover": 1.7})

    row = result[result["year"] == 2024].iloc[0]
    assert row["factor_name"] == "momentum_20d"
    assert round(row["ic_mean"], 6) == 0.01
    assert round(row["rank_ic_mean"], 6) == 0.06
    assert row["positive_ic_ratio"] == 0.5
    assert round(row["total_return"], 6) == round(1.05 / 1.10 - 1, 6)
    assert round(row["benchmark_total_return"], 6) == round(1.02 / 1.05 - 1, 6)
    assert round(row["turnover"], 6) == 0.7
    assert row["full_period_turnover"] == 1.7


def test_summarize_factor_rolling_outputs_stability_columns():
    result = summarize_factor_rolling(
        make_evaluation_frame(),
        make_backtest_frame(),
        rank_ic_window=2,
        return_window=2,
    )

    assert {
        "trade_date",
        "factor_name",
        "rolling_60d_rank_ic_mean",
        "rolling_120d_excess_return",
        "rolling_120d_max_drawdown",
    } == set(result.columns)
    assert pd.notna(result.loc[1, "rolling_60d_rank_ic_mean"])
    assert pd.notna(result.loc[2, "rolling_120d_excess_return"])
