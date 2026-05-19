import pandas as pd


def winsorize_cross_section(
    frame: pd.DataFrame,
    factor_columns: list[str],
    lower_quantile: float = 0.01,
    upper_quantile: float = 0.99,
) -> pd.DataFrame:
    if not 0 <= lower_quantile < upper_quantile <= 1:
        raise ValueError("lower_quantile and upper_quantile must satisfy 0 <= lower < upper <= 1")
    if "trade_date" not in frame.columns:
        raise ValueError("Missing required column: trade_date")

    result = frame.copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"]).astype("datetime64[ns]")
    grouped = result.groupby("trade_date")
    for column in factor_columns:
        if column not in result.columns:
            raise ValueError(f"Missing factor column: {column}")
        lower = grouped[column].transform(lambda series: series.quantile(lower_quantile))
        upper = grouped[column].transform(lambda series: series.quantile(upper_quantile))
        result[f"{column}_winsorized"] = result[column].clip(lower=lower, upper=upper)
    return result


def zscore_cross_section(
    frame: pd.DataFrame,
    factor_columns: list[str],
) -> pd.DataFrame:
    if "trade_date" not in frame.columns:
        raise ValueError("Missing required column: trade_date")

    result = frame.copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"]).astype("datetime64[ns]")
    grouped = result.groupby("trade_date")
    for column in factor_columns:
        if column not in result.columns:
            raise ValueError(f"Missing factor column: {column}")
        mean = grouped[column].transform("mean")
        std = grouped[column].transform("std")
        result[f"{column}_zscore"] = (result[column] - mean) / std
        result.loc[std.fillna(0) == 0, f"{column}_zscore"] = 0.0
    return result


def add_standardized_factors(
    frame: pd.DataFrame,
    factor_columns: list[str],
    lower_quantile: float = 0.01,
    upper_quantile: float = 0.99,
) -> pd.DataFrame:
    winsorized = winsorize_cross_section(frame, factor_columns, lower_quantile, upper_quantile)
    winsorized_columns = [f"{column}_winsorized" for column in factor_columns]
    result = zscore_cross_section(winsorized, winsorized_columns)
    rename_map = {f"{column}_winsorized_zscore": f"{column}_zscore" for column in factor_columns}
    return result.rename(columns=rename_map)
