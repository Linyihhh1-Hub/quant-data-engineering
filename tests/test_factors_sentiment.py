import pandas as pd

from quant_data.factors.sentiment import (
    MARKET_SENTIMENT_JOIN_COLUMNS,
    compute_market_sentiment,
    join_market_sentiment,
)


def make_sentiment_daily_frame(days: int = 80) -> pd.DataFrame:
    rows = []
    symbols = ["000001.SZ", "000002.SZ", "600000.SH", "600519.SH"]
    returns = [0.04, 0.01, -0.02, -0.04]
    for idx in range(days):
        day = pd.Timestamp("2024-01-01") + pd.Timedelta(days=idx)
        for symbol_index, symbol in enumerate(symbols):
            ret = returns[(idx + symbol_index) % len(returns)]
            rows.append(
                {
                    "trade_date": day,
                    "symbol": symbol,
                    "return_1d": ret,
                    "volume": 1000 + idx * 10 + symbol_index,
                    "amount": 10000 + idx * 100 + symbol_index,
                }
            )
    return pd.DataFrame(rows)


def test_compute_market_sentiment_builds_expected_columns():
    result = compute_market_sentiment(make_sentiment_daily_frame())

    assert result.columns.tolist() == [
        "trade_date",
        "stock_count",
        "market_up_ratio",
        "market_down_ratio",
        "market_strong_ratio",
        "market_weak_ratio",
        "market_amount",
        "market_volume",
        "market_amount_ratio_20d",
        "market_volume_ratio_20d",
        "market_return_mean",
        "market_return_median",
        "market_return_positive_mean",
        "market_return_negative_mean",
        "profit_effect",
        "market_sentiment_score",
    ]


def test_compute_market_sentiment_calculates_market_breadth_and_profit_effect():
    result = compute_market_sentiment(make_sentiment_daily_frame(days=25))
    first = result.iloc[0]

    assert first["stock_count"] == 4
    assert first["market_up_ratio"] == 0.5
    assert first["market_down_ratio"] == 0.5
    assert first["market_strong_ratio"] == 0.25
    assert first["market_weak_ratio"] == 0.25
    assert round(first["market_return_positive_mean"], 6) == 0.025
    assert round(first["market_return_negative_mean"], 6) == -0.03
    assert round(first["profit_effect"], 6) == -0.005


def test_compute_market_sentiment_calculates_rolling_activity_ratios_and_score():
    result = compute_market_sentiment(make_sentiment_daily_frame(days=80))

    assert pd.isna(result.loc[18, "market_amount_ratio_20d"])
    assert result.loc[19, "market_amount_ratio_20d"] > 0
    assert pd.isna(result.loc[77, "market_sentiment_score"])
    assert pd.notna(result.loc[78, "market_sentiment_score"])


def test_join_market_sentiment_adds_market_state_to_factor_wide_table():
    daily = make_sentiment_daily_frame(days=80)
    sentiment = compute_market_sentiment(daily)
    factors = daily[["trade_date", "symbol"]].copy()
    factors["momentum_20d"] = 0.1

    result = join_market_sentiment(factors, sentiment)

    for column in MARKET_SENTIMENT_JOIN_COLUMNS:
        assert column in result.columns
    assert len(result) == len(factors)
