from importlib import import_module
from pathlib import Path

import pandas as pd

from quant_data.storage.parquet import write_parquet

INDEX_COLUMNS = ["trade_date", "symbol", "open", "high", "low", "close", "volume", "amount"]
INDEX_COLUMN_MAP = {
    "日期": "trade_date",
    "date": "trade_date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "amount": "amount",
}


def _load_akshare():
    try:
        return import_module("akshare")
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError("AkShare is not installed. Install project dependencies before index ingestion.") from error


def _standardize_index_frame(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=INDEX_COLUMNS)
    result = raw.rename(columns=INDEX_COLUMN_MAP)
    missing_columns = set(INDEX_COLUMNS) - {"symbol", "amount"} - set(result.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"AkShare index response missing required columns: {missing}")
    result["symbol"] = symbol
    if "amount" not in result.columns:
        result["amount"] = 0.0
    result = result[INDEX_COLUMNS].copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"]).astype("datetime64[ns]")
    return result.sort_values("trade_date").reset_index(drop=True)


def fetch_hs300_index(start_date: str, end_date: str) -> pd.DataFrame:
    akshare = _load_akshare()
    if hasattr(akshare, "stock_zh_index_daily"):
        raw = akshare.stock_zh_index_daily(symbol="sh000300")
        frame = _standardize_index_frame(raw, "000300.SH")
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        return frame[(frame["trade_date"] >= start) & (frame["trade_date"] <= end)].reset_index(drop=True)
    raw = akshare.index_zh_a_hist(symbol="000300", period="daily", start_date=start_date, end_date=end_date)
    return _standardize_index_frame(raw, "000300.SH")


def write_hs300_index(start_date: str, end_date: str, output_path: str | Path) -> Path:
    return write_parquet(fetch_hs300_index(start_date, end_date), output_path)
