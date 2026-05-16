import pandas as pd


def add_forward_return(daily_bars: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    required_columns = {"trade_date", "symbol", "close"}
    missing_columns = required_columns - set(daily_bars.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")

    result = daily_bars.copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"]).astype("datetime64[ns]")
    result = result.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    next_close = result.groupby("symbol")["close"].shift(-horizon)
    result["forward_return"] = next_close / result["close"] - 1
    return result


def _joined_factor_returns(
    factors: pd.DataFrame,
    daily_bars: pd.DataFrame,
    factor_name: str,
    horizon: int,
) -> pd.DataFrame:
    required_factor_columns = {"trade_date", "symbol", factor_name}
    missing_factor_columns = required_factor_columns - set(factors.columns)
    if missing_factor_columns:
        missing = ", ".join(sorted(missing_factor_columns))
        raise ValueError(f"Missing required factor columns: {missing}")

    factor_frame = factors[["trade_date", "symbol", factor_name]].copy()
    factor_frame["trade_date"] = pd.to_datetime(factor_frame["trade_date"]).astype("datetime64[ns]")
    returns = add_forward_return(daily_bars, horizon)[
        ["trade_date", "symbol", "forward_return"]
    ]
    joined = factor_frame.merge(returns, on=["trade_date", "symbol"], how="inner")
    return joined.dropna(subset=[factor_name, "forward_return"])


def compute_ic_report(
    factors: pd.DataFrame,
    daily_bars: pd.DataFrame,
    factor_name: str,
    horizon: int = 5,
) -> pd.DataFrame:
    joined = _joined_factor_returns(factors, daily_bars, factor_name, horizon)
    rows = []
    for trade_date, group in joined.groupby("trade_date"):
        if len(group) < 2 or group[factor_name].nunique() < 2 or group["forward_return"].nunique() < 2:
            continue
        rows.append(
            {
                "trade_date": trade_date,
                "factor_name": factor_name,
                "ic": group[factor_name].corr(group["forward_return"], method="pearson"),
                "rank_ic": group[factor_name].rank().corr(group["forward_return"].rank(), method="pearson"),
            }
        )
    return pd.DataFrame(rows, columns=["trade_date", "factor_name", "ic", "rank_ic"])


def compute_group_return_report(
    factors: pd.DataFrame,
    daily_bars: pd.DataFrame,
    factor_name: str,
    horizon: int = 5,
    groups: int = 5,
) -> pd.DataFrame:
    joined = _joined_factor_returns(factors, daily_bars, factor_name, horizon)
    rows = []
    for trade_date, group in joined.groupby("trade_date"):
        if group[factor_name].nunique() < groups:
            continue
        ranked = group.copy()
        ranked["factor_group"] = pd.qcut(
            ranked[factor_name], q=groups, labels=False, duplicates="drop"
        )
        if ranked["factor_group"].nunique() < groups:
            continue
        bottom_return = ranked.loc[ranked["factor_group"] == 0, "forward_return"].mean()
        top_return = ranked.loc[ranked["factor_group"] == groups - 1, "forward_return"].mean()
        rows.append(
            {
                "trade_date": trade_date,
                "factor_name": factor_name,
                "top_group_return": top_return,
                "bottom_group_return": bottom_return,
                "long_short_return": top_return - bottom_return,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "trade_date",
            "factor_name",
            "top_group_return",
            "bottom_group_return",
            "long_short_return",
        ],
    )


def evaluate_factor(
    factors: pd.DataFrame,
    daily_bars: pd.DataFrame,
    factor_name: str,
    horizon: int = 5,
    groups: int = 5,
) -> pd.DataFrame:
    ic_report = compute_ic_report(factors, daily_bars, factor_name, horizon)
    group_report = compute_group_return_report(
        factors, daily_bars, factor_name, horizon, groups
    )
    return ic_report.merge(group_report, on=["trade_date", "factor_name"], how="inner")


