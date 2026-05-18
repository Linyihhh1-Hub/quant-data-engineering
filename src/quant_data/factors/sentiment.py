import pandas as pd

MARKET_SENTIMENT_COLUMNS = [
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

MARKET_SENTIMENT_JOIN_COLUMNS = [
    "market_up_ratio",
    "market_strong_ratio",
    "market_weak_ratio",
    "market_amount_ratio_20d",
    "profit_effect",
    "market_sentiment_score",
]

REQUIRED_COLUMNS = {"trade_date", "symbol", "return_1d", "volume", "amount"}


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    rolling_mean = series.rolling(window=window, min_periods=window).mean()
    rolling_std = series.rolling(window=window, min_periods=window).std()
    zscore = (series - rolling_mean) / rolling_std
    return zscore.mask((rolling_std == 0) & rolling_mean.notna(), 0.0)


def compute_market_sentiment(
    daily_bars: pd.DataFrame,
    activity_window: int = 20,
    zscore_window: int = 60,
    strong_threshold: float = 0.03,
    weak_threshold: float = -0.03,
) -> pd.DataFrame:
    missing_columns = REQUIRED_COLUMNS - set(daily_bars.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")

    frame = daily_bars.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).astype("datetime64[ns]")
    frame["return_1d"] = pd.to_numeric(frame["return_1d"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    frame = frame.dropna(subset=["return_1d"])

    grouped = frame.groupby("trade_date", sort=True)
    result = grouped.agg(
        stock_count=("symbol", "nunique"),
        market_amount=("amount", "sum"),
        market_volume=("volume", "sum"),
        market_return_mean=("return_1d", "mean"),
        market_return_median=("return_1d", "median"),
    ).reset_index()

    positive = frame[frame["return_1d"] > 0].groupby("trade_date")["return_1d"].mean()
    negative = frame[frame["return_1d"] < 0].groupby("trade_date")["return_1d"].mean()
    result["market_return_positive_mean"] = result["trade_date"].map(positive).fillna(0.0)
    result["market_return_negative_mean"] = result["trade_date"].map(negative).fillna(0.0)
    result["profit_effect"] = result["market_return_positive_mean"] - result["market_return_negative_mean"].abs()

    counts = grouped["return_1d"].count().rename("valid_count")
    up_counts = frame[frame["return_1d"] > 0].groupby("trade_date")["return_1d"].count()
    down_counts = frame[frame["return_1d"] < 0].groupby("trade_date")["return_1d"].count()
    strong_counts = frame[frame["return_1d"] > strong_threshold].groupby("trade_date")["return_1d"].count()
    weak_counts = frame[frame["return_1d"] < weak_threshold].groupby("trade_date")["return_1d"].count()
    result["market_up_ratio"] = result["trade_date"].map(up_counts).fillna(0) / result["trade_date"].map(counts)
    result["market_down_ratio"] = result["trade_date"].map(down_counts).fillna(0) / result["trade_date"].map(counts)
    result["market_strong_ratio"] = result["trade_date"].map(strong_counts).fillna(0) / result["trade_date"].map(counts)
    result["market_weak_ratio"] = result["trade_date"].map(weak_counts).fillna(0) / result["trade_date"].map(counts)

    result = result.sort_values("trade_date").reset_index(drop=True)
    result["market_amount_ratio_20d"] = result["market_amount"] / result["market_amount"].rolling(
        window=activity_window, min_periods=activity_window
    ).mean()
    result["market_volume_ratio_20d"] = result["market_volume"] / result["market_volume"].rolling(
        window=activity_window, min_periods=activity_window
    ).mean()

    sentiment_parts = {
        "up": _rolling_zscore(result["market_up_ratio"], zscore_window),
        "strong": _rolling_zscore(result["market_strong_ratio"], zscore_window),
        "weak": _rolling_zscore(result["market_weak_ratio"], zscore_window),
        "amount": _rolling_zscore(result["market_amount_ratio_20d"], zscore_window),
        "profit": _rolling_zscore(result["profit_effect"], zscore_window),
    }
    result["market_sentiment_score"] = (
        sentiment_parts["up"]
        + sentiment_parts["strong"]
        - sentiment_parts["weak"]
        + sentiment_parts["amount"]
        + sentiment_parts["profit"]
    )

    return result[["trade_date", *MARKET_SENTIMENT_COLUMNS]]


def join_market_sentiment(
    factor_wide: pd.DataFrame,
    market_sentiment: pd.DataFrame,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    join_columns = columns or MARKET_SENTIMENT_JOIN_COLUMNS
    missing_columns = {"trade_date", *join_columns} - set(market_sentiment.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing market sentiment columns: {missing}")

    factors = factor_wide.copy()
    factors["trade_date"] = pd.to_datetime(factors["trade_date"]).astype("datetime64[ns]")
    sentiment = market_sentiment[["trade_date", *join_columns]].copy()
    sentiment["trade_date"] = pd.to_datetime(sentiment["trade_date"]).astype("datetime64[ns]")
    return factors.merge(sentiment, on="trade_date", how="left")
