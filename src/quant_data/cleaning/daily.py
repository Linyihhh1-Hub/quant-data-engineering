import pandas as pd

NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]


def normalize_symbol(symbol: str) -> str:
    value = str(symbol).strip()
    if value.endswith((".SZ", ".SH", ".BJ")):
        return value
    # A 股常见代码前缀：0/3 深市，6 沪市，4/8 北交所。
    if value.startswith(("0", "3")):
        return f"{value}.SZ"
    if value.startswith("6"):
        return f"{value}.SH"
    if value.startswith(("4", "8")):
        return f"{value}.BJ"
    return value


def clean_daily_bars(frame: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"trade_date", "symbol", *NUMERIC_COLUMNS}
    missing_columns = required_columns - set(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")

    result = frame.copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"]).astype("datetime64[ns]")
    result["symbol"] = result["symbol"].map(normalize_symbol)

    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    # 同一股票同一交易日只保留最后一条，模拟数据落表时的幂等覆盖语义。
    result = result.drop_duplicates(subset=["trade_date", "symbol"], keep="last")
    result = result.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    # 收益率必须按股票分组计算，避免不同股票之间发生收益串线。
    result["return_1d"] = result.groupby("symbol")["close"].pct_change()
    return result
