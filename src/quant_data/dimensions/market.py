from importlib import import_module
from pathlib import Path

import pandas as pd

from quant_data.cleaning.daily import normalize_symbol
from quant_data.storage.parquet import write_parquet


def _load_akshare():
    try:
        return import_module("akshare")
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError("AkShare is required for building market dimensions.") from error


def _pick_column(frame: pd.DataFrame, candidates: list[str]) -> str:
    for column in candidates:
        if column in frame.columns:
            return column
    raise ValueError(f"Missing expected column, candidates={candidates}, actual={frame.columns.tolist()}")


def _exchange(raw_symbol: str) -> str:
    if raw_symbol.startswith(("0", "3")):
        return "SZ"
    if raw_symbol.startswith("6"):
        return "SH"
    if raw_symbol.startswith(("4", "8")):
        return "BJ"
    return ""


def _raw_symbol(value: object) -> str:
    text = str(value).strip()
    if "." in text:
        text = text.split(".")[0]
    return text.zfill(6)


def build_trade_calendar(start_date: str, end_date: str) -> pd.DataFrame:
    akshare = _load_akshare()
    raw = akshare.tool_trade_date_hist_sina()
    date_col = _pick_column(raw, ["trade_date", "交易日", "date"])
    calendar = pd.DataFrame({"trade_date": pd.to_datetime(raw[date_col])})
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    calendar = calendar[(calendar["trade_date"] >= start) & (calendar["trade_date"] <= end)]
    calendar = calendar.drop_duplicates().sort_values("trade_date").reset_index(drop=True)
    calendar["is_open"] = True
    calendar["pre_trade_date"] = calendar["trade_date"].shift(1)
    calendar["next_trade_date"] = calendar["trade_date"].shift(-1)
    return calendar[["trade_date", "is_open", "pre_trade_date", "next_trade_date"]]


def build_stock_basic() -> pd.DataFrame:
    akshare = _load_akshare()
    raw = akshare.stock_info_a_code_name()
    code_col = _pick_column(raw, ["code", "代码", "symbol"])
    name_col = _pick_column(raw, ["name", "名称", "股票简称"])
    result = pd.DataFrame(
        {
            "raw_symbol": raw[code_col].map(_raw_symbol),
            "name": raw[name_col].astype(str).str.strip(),
        }
    )
    result["symbol"] = result["raw_symbol"].map(normalize_symbol)
    result["exchange"] = result["raw_symbol"].map(_exchange)

    try:
        st_raw = akshare.stock_zh_a_st_em()
        st_code_col = _pick_column(st_raw, ["代码", "code", "symbol"])
        st_symbols = set(st_raw[st_code_col].map(_raw_symbol))
    except Exception:  # noqa: BLE001 - ST 接口偶发不可用时，保留基础信息并默认非 ST。
        st_symbols = set()
    name_marks_st = result["name"].str.upper().str.contains("ST", regex=False)
    result["is_st"] = result["raw_symbol"].isin(st_symbols) | name_marks_st
    result = result.drop_duplicates(subset=["raw_symbol"], keep="last")
    result = result.sort_values("raw_symbol").reset_index(drop=True)
    return result[["symbol", "raw_symbol", "name", "exchange", "is_st"]]


def build_hs300_symbol_pool(filter_st: bool = True) -> pd.DataFrame:
    akshare = _load_akshare()
    if hasattr(akshare, "index_stock_cons_csindex"):
        raw = akshare.index_stock_cons_csindex(symbol="000300")
    else:
        raw = akshare.index_stock_cons(symbol="000300")
    code_col = _pick_column(raw, ["品种代码", "成分券代码", "code", "证券代码"])
    name_col = _pick_column(raw, ["品种名称", "成分券名称", "name", "证券简称"])
    pool = pd.DataFrame(
        {
            "symbol": raw[code_col].map(_raw_symbol),
            "name": raw[name_col].astype(str).str.strip(),
        }
    )
    if filter_st:
        basic = build_stock_basic()[["raw_symbol", "is_st"]]
        pool = pool.merge(basic, left_on="symbol", right_on="raw_symbol", how="left")
        pool = pool[pool["is_st"] != True]  # noqa: E712 - pandas 布尔列需要保留 NaN 语义。
    pool = pool.drop_duplicates(subset=["symbol"], keep="last")
    return pool[["symbol", "name"]].sort_values("symbol").reset_index(drop=True)


def write_trade_calendar(start_date: str, end_date: str, output_path: str | Path) -> Path:
    return write_parquet(build_trade_calendar(start_date, end_date), output_path)


def write_stock_basic(output_path: str | Path) -> Path:
    return write_parquet(build_stock_basic(), output_path)


def write_hs300_symbol_pool(output_path: str | Path, filter_st: bool = True) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pool = build_hs300_symbol_pool(filter_st=filter_st)
    pool.to_csv(path, index=False, encoding="utf-8")
    return path
