from importlib import import_module
from pathlib import Path
from typing import Iterable

import pandas as pd

from quant_data.storage.parquet import write_parquet

AKSHARE_COLUMN_MAP = {
    "日期": "trade_date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
    "成交额": "amount",
}

ODS_COLUMNS = ["trade_date", "symbol", "open", "high", "low", "close", "volume", "amount"]


def _load_akshare():
    try:
        return import_module("akshare")
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "AkShare is not installed. Install project dependencies with "
            '`python -m pip install -e ".[dev]"` before running real ingestion.'
        ) from error


def fetch_stock_daily(
    symbol: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
) -> pd.DataFrame:
    akshare = _load_akshare()
    raw = akshare.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )
    if raw.empty:
        return pd.DataFrame(columns=ODS_COLUMNS)

    result = raw.rename(columns=AKSHARE_COLUMN_MAP)
    missing_columns = set(ODS_COLUMNS) - {"symbol"} - set(result.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"AkShare response missing required columns: {missing}")

    # ODS 层只做字段标准化和股票代码补充，不在采集阶段做业务清洗。
    result["symbol"] = symbol
    return result[ODS_COLUMNS]


def ingest_stock_daily(
    symbols: Iterable[str],
    start_date: str,
    end_date: str,
    output_path: str | Path,
    report_path: str | Path,
    adjust: str = "qfq",
) -> tuple[Path, Path]:
    frames = []
    report_rows = []
    for symbol in symbols:
        normalized_symbol = symbol.strip()
        if not normalized_symbol:
            continue
        try:
            frame = fetch_stock_daily(normalized_symbol, start_date, end_date, adjust=adjust)
        except Exception as error:  # noqa: BLE001 - 采集阶段需要记录单票失败并继续其他股票。
            report_rows.append(
                {
                    "symbol": normalized_symbol,
                    "status": "FAILED",
                    "row_count": 0,
                    "message": str(error),
                }
            )
            continue
        if not frame.empty:
            frames.append(frame)
            report_rows.append(
                {
                    "symbol": normalized_symbol,
                    "status": "SUCCESS",
                    "row_count": len(frame),
                    "message": "",
                }
            )
        else:
            report_rows.append(
                {
                    "symbol": normalized_symbol,
                    "status": "EMPTY",
                    "row_count": 0,
                    "message": "AkShare returned empty data",
                }
            )

    report_output = write_parquet(pd.DataFrame(report_rows), report_path)
    if not frames:
        detail = "; ".join(row["message"] for row in report_rows if row["status"] == "FAILED")
        raise RuntimeError(f"No stock data fetched. Failures: {detail}")

    combined = pd.concat(frames, ignore_index=True)
    data_output = write_parquet(combined, output_path)
    return data_output, report_output
