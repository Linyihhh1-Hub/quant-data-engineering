import pandas as pd

from quant_data.factors.preprocessing import add_standardized_factors

FACTOR_COLUMNS = [
    "momentum_20d",
    "relative_strength_20d",
    "relative_strength_60d",
    "reversal_5d",
    "volatility_20d",
    "volume_ratio_5d",
    "ma_bias_20d",
]
WINSORIZED_FACTOR_COLUMNS = [f"{column}_winsorized" for column in FACTOR_COLUMNS]
ZSCORE_FACTOR_COLUMNS = [f"{column}_zscore" for column in FACTOR_COLUMNS]
COMPOSITE_FACTOR_COLUMNS = [
    "low_volatility_ma_bias_score",
    "low_volatility_ma_bias_relative_strength_score",
]
ALL_FACTOR_COLUMNS = [*FACTOR_COLUMNS, *WINSORIZED_FACTOR_COLUMNS, *ZSCORE_FACTOR_COLUMNS, *COMPOSITE_FACTOR_COLUMNS]

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
    result["momentum_60d"] = close.pct_change(periods=60)
    daily_mean_20d = result.groupby("trade_date")["momentum_20d"].transform("mean")
    daily_mean_60d = result.groupby("trade_date")["momentum_60d"].transform("mean")
    result["relative_strength_20d"] = result["momentum_20d"] - daily_mean_20d
    result["relative_strength_60d"] = result["momentum_60d"] - daily_mean_60d
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

    result = add_standardized_factors(result, FACTOR_COLUMNS)
    result["low_volatility_ma_bias_score"] = (
        result["volatility_20d_zscore"] + result["ma_bias_20d_zscore"]
    ) / 2
    result["low_volatility_ma_bias_relative_strength_score"] = (
        result["volatility_20d_zscore"]
        + result["ma_bias_20d_zscore"]
        - result["relative_strength_20d_zscore"]
        - result["relative_strength_60d_zscore"]
    ) / 4
    return result[["trade_date", "symbol", *ALL_FACTOR_COLUMNS]]
