import pandas as pd

FACTOR_COLUMNS = [
    "momentum_20d",
    "reversal_5d",
    "volatility_20d",
    "volume_ratio_5d",
    "ma_bias_20d",
]

REQUIRED_COLUMNS = {"trade_date", "symbol", "close", "volume", "return_1d"}


def compute_baseline_factors(frame: pd.DataFrame) -> pd.DataFrame:
    missing_columns = REQUIRED_COLUMNS - set(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")

    result = frame.copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"]).astype("datetime64[ns]")
    result = result.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    # 所有滚动窗口都必须按股票分组计算，避免把 A 股票历史价格滚到 B 股票上。
    grouped = result.groupby("symbol", group_keys=False)
    close = grouped["close"]
    volume = grouped["volume"]

    result["momentum_20d"] = close.pct_change(periods=20)
    result["reversal_5d"] = -1 * close.pct_change(periods=5)
    result["volatility_20d"] = grouped["return_1d"].transform(
        lambda series: series.rolling(window=20, min_periods=20).std()
    )
    result["volume_ratio_5d"] = result["volume"] / volume.transform(
        lambda series: series.rolling(window=5, min_periods=5).mean()
    )
    result["ma_bias_20d"] = result["close"] / close.transform(
        lambda series: series.rolling(window=20, min_periods=20).mean()
    ) - 1

    return result[["trade_date", "symbol", *FACTOR_COLUMNS]]
