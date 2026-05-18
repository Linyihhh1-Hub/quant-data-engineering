from importlib import import_module
from pathlib import Path
from time import sleep
from typing import Iterable
from uuid import uuid4

import pandas as pd

from quant_data.storage.parquet import read_parquet
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


def _format_akshare_date(value: pd.Timestamp) -> str:
    return value.strftime("%Y%m%d")


def _next_fetch_start(existing: pd.DataFrame, symbol: str, requested_start: str) -> str:
    if existing.empty or "symbol" not in existing.columns or "trade_date" not in existing.columns:
        return requested_start
    symbol_rows = existing[existing["symbol"].astype(str).str.strip() == symbol]
    if symbol_rows.empty:
        return requested_start
    max_date = pd.to_datetime(symbol_rows["trade_date"]).max()
    next_date = max_date + pd.Timedelta(days=1)
    requested = pd.to_datetime(requested_start)
    return _format_akshare_date(max(next_date, requested))


def _append_run_log(
    run_log_path: str | Path,
    row: dict[str, object],
) -> Path:
    path = Path(run_log_path)
    if path.exists():
        existing = read_parquet(path)
        frame = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
    else:
        frame = pd.DataFrame([row])
    return write_parquet(frame, path)


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
    retries: int = 2,
    retry_wait_seconds: float = 1.0,
    incremental: bool = False,
    run_log_path: str | Path | None = None,
) -> tuple[Path, Path]:
    if retries < 0:
        raise ValueError("retries must be >= 0")
    if retry_wait_seconds < 0:
        raise ValueError("retry_wait_seconds must be >= 0")

    started_at = pd.Timestamp.now(tz="UTC")
    output = Path(output_path)
    existing = read_parquet(output) if incremental and output.exists() else pd.DataFrame(columns=ODS_COLUMNS)
    frames = []
    report_rows = []
    normalized_symbols = [symbol.strip() for symbol in symbols if symbol.strip()]
    requested_end = pd.to_datetime(end_date)
    for normalized_symbol in normalized_symbols:
        fetch_start_date = _next_fetch_start(existing, normalized_symbol, start_date) if incremental else start_date
        if pd.to_datetime(fetch_start_date) > requested_end:
            report_rows.append(
                {
                    "symbol": normalized_symbol,
                    "status": "SKIPPED",
                    "row_count": 0,
                    "message": "Already up to date",
                }
            )
            continue
        last_error: Exception | None = None
        try:
            # 外部行情接口偶发网络失败时，按单只股票重试，避免整批采集被短暂抖动击穿。
            for attempt in range(retries + 1):
                try:
                    frame = fetch_stock_daily(normalized_symbol, fetch_start_date, end_date, adjust=adjust)
                    break
                except Exception as error:  # noqa: BLE001 - 这里需要保留原始异常写入采集报告。
                    last_error = error
                    if attempt < retries:
                        sleep(retry_wait_seconds)
            else:
                raise last_error or RuntimeError("Unknown ingestion error")
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
    if not frames and existing.empty:
        detail = "; ".join(row["message"] for row in report_rows if row["status"] == "FAILED")
        raise RuntimeError(f"No stock data fetched. Failures: {detail}")

    combined = pd.concat([existing, *frames], ignore_index=True)
    combined["trade_date"] = pd.to_datetime(combined["trade_date"]).astype("datetime64[ns]")
    combined = combined.drop_duplicates(subset=["trade_date", "symbol"], keep="last")
    combined = combined.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    data_output = write_parquet(combined, output_path)
    if run_log_path:
        ended_at = pd.Timestamp.now(tz="UTC")
        statuses = pd.Series([row["status"] for row in report_rows], dtype="string")
        _append_run_log(
            run_log_path,
            {
                "run_id": str(uuid4()),
                "started_at": started_at,
                "ended_at": ended_at,
                "requested_start_date": start_date,
                "requested_end_date": end_date,
                "symbols_count": len(normalized_symbols),
                "success_count": int((statuses == "SUCCESS").sum()),
                "failed_count": int((statuses == "FAILED").sum()),
                "empty_count": int((statuses == "EMPTY").sum()),
                "skipped_count": int((statuses == "SKIPPED").sum()),
                "output_rows": len(combined),
                "incremental": incremental,
            },
        )
    return data_output, report_output
