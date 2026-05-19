import sys
import types

import pandas as pd

from quant_data.ingestion.akshare_a_share import fetch_stock_daily, ingest_stock_daily


def install_fake_akshare(monkeypatch, fail_symbols: set[str] | None = None) -> list[dict[str, str]]:
    calls = []
    fail_symbols = fail_symbols or set()
    fake = types.ModuleType("akshare")

    def stock_zh_a_hist(symbol: str, period: str, start_date: str, end_date: str, adjust: str):
        calls.append(
            {
                "symbol": symbol,
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "adjust": adjust,
            }
        )
        if symbol in fail_symbols:
            raise RuntimeError(f"failed: {symbol}")
        return pd.DataFrame(
            [
                {
                    "日期": "2024-01-02",
                    "开盘": 10.0,
                    "最高": 10.5,
                    "最低": 9.8,
                    "收盘": 10.2,
                    "成交量": 1000,
                    "成交额": 10200,
                }
            ]
        )

    fake.stock_zh_a_hist = stock_zh_a_hist
    monkeypatch.setitem(sys.modules, "akshare", fake)
    return calls


def test_fetch_stock_daily_standardizes_akshare_columns(monkeypatch):
    calls = install_fake_akshare(monkeypatch)

    result = fetch_stock_daily("000001", "20240101", "20240131", adjust="qfq")

    assert calls == [
        {
            "symbol": "000001",
            "period": "daily",
            "start_date": "20240101",
            "end_date": "20240131",
            "adjust": "qfq",
        }
    ]
    assert result.columns.tolist() == [
        "trade_date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
    ]
    assert result.loc[0, "symbol"] == "000001"
    assert result.loc[0, "close"] == 10.2


def test_fetch_stock_daily_falls_back_to_daily_endpoint(monkeypatch):
    fake = types.ModuleType("akshare")
    calls = []

    def stock_zh_a_hist(symbol: str, period: str, start_date: str, end_date: str, adjust: str):
        calls.append(("hist", symbol, start_date, end_date, adjust))
        raise RuntimeError("eastmoney failed")

    def stock_zh_a_daily(symbol: str, start_date: str, end_date: str, adjust: str):
        calls.append(("daily", symbol, start_date, end_date, adjust))
        return pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2024-01-02").date(),
                    "open": 5.87,
                    "high": 5.98,
                    "low": 5.81,
                    "close": 5.94,
                    "volume": 36905402,
                    "amount": 244294646,
                }
            ]
        )

    fake.stock_zh_a_hist = stock_zh_a_hist
    fake.stock_zh_a_daily = stock_zh_a_daily
    monkeypatch.setitem(sys.modules, "akshare", fake)

    result = fetch_stock_daily("000157", "20240101", "20241231", adjust="qfq")

    assert calls == [
        ("hist", "000157", "20240101", "20241231", "qfq"),
        ("daily", "sz000157", "20240101", "20241231", "qfq"),
    ]
    assert result["symbol"].tolist() == ["000157"]
    assert result.loc[0, "close"] == 5.94


def test_ingest_stock_daily_writes_successful_symbols_and_skips_failures(monkeypatch, tmp_path):
    install_fake_akshare(monkeypatch, fail_symbols={"600000"})
    output_path = tmp_path / "ods" / "stock_daily.parquet"

    result_path, report_path = ingest_stock_daily(
        symbols=["000001", "600000"],
        start_date="20240101",
        end_date="20240131",
        output_path=output_path,
        report_path=tmp_path / "reports" / "ingestion_report.parquet",
        adjust="qfq",
    )

    result = pd.read_parquet(result_path)
    report = pd.read_parquet(report_path)
    assert result_path == output_path
    assert result["symbol"].tolist() == ["000001"]
    assert output_path.exists()
    assert report["symbol"].tolist() == ["000001", "600000"]
    assert report["status"].tolist() == ["SUCCESS", "FAILED"]
    assert report.loc[0, "row_count"] == 1
    assert "failed: 600000" in report.loc[1, "message"]


def test_ingest_stock_daily_retries_transient_symbol_failure(monkeypatch, tmp_path):
    fake = types.ModuleType("akshare")
    attempts = {"000001": 0}

    def stock_zh_a_hist(symbol: str, period: str, start_date: str, end_date: str, adjust: str):
        attempts[symbol] += 1
        if attempts[symbol] == 1:
            raise RuntimeError("temporary network error")
        return pd.DataFrame(
            [
                {
                    "日期": "2024-01-02",
                    "开盘": 10.0,
                    "最高": 10.5,
                    "最低": 9.8,
                    "收盘": 10.2,
                    "成交量": 1000,
                    "成交额": 10200,
                }
            ]
        )

    fake.stock_zh_a_hist = stock_zh_a_hist
    monkeypatch.setitem(sys.modules, "akshare", fake)

    result_path, report_path = ingest_stock_daily(
        symbols=["000001"],
        start_date="20240101",
        end_date="20240131",
        output_path=tmp_path / "ods" / "stock_daily.parquet",
        report_path=tmp_path / "reports" / "ingestion_report.parquet",
        adjust="qfq",
        retries=1,
        retry_wait_seconds=0,
    )

    result = pd.read_parquet(result_path)
    report = pd.read_parquet(report_path)
    assert attempts["000001"] == 2
    assert result["symbol"].tolist() == ["000001"]
    assert report["status"].tolist() == ["SUCCESS"]


def test_ingest_stock_daily_incremental_fetches_only_missing_dates(monkeypatch, tmp_path):
    calls = []
    fake = types.ModuleType("akshare")
    output_path = tmp_path / "ods" / "stock_daily.parquet"
    output_path.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "trade_date": "2024-01-02",
                "symbol": "000001",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000,
                "amount": 10200,
            }
        ]
    ).to_parquet(output_path, index=False)

    def stock_zh_a_hist(symbol: str, period: str, start_date: str, end_date: str, adjust: str):
        calls.append({"symbol": symbol, "start_date": start_date, "end_date": end_date})
        return pd.DataFrame(
            [
                {
                    "日期": pd.to_datetime(start_date).strftime("%Y-%m-%d"),
                    "开盘": 11.0,
                    "最高": 11.5,
                    "最低": 10.8,
                    "收盘": 11.2,
                    "成交量": 1100,
                    "成交额": 11200,
                }
            ]
        )

    fake.stock_zh_a_hist = stock_zh_a_hist
    monkeypatch.setitem(sys.modules, "akshare", fake)

    result_path, report_path = ingest_stock_daily(
        symbols=["000001", "600000"],
        start_date="20240101",
        end_date="20240105",
        output_path=output_path,
        report_path=tmp_path / "reports" / "ingestion_report.parquet",
        incremental=True,
        retry_wait_seconds=0,
    )

    result = pd.read_parquet(result_path)
    report = pd.read_parquet(report_path)
    assert calls == [
        {"symbol": "000001", "start_date": "20240101", "end_date": "20240101"},
        {"symbol": "000001", "start_date": "20240103", "end_date": "20240105"},
        {"symbol": "600000", "start_date": "20240101", "end_date": "20240105"},
    ]
    assert len(result) == 4
    assert result.duplicated(subset=["trade_date", "symbol"]).sum() == 0
    assert report["status"].tolist() == ["SUCCESS", "SUCCESS"]


def test_ingest_stock_daily_writes_run_log(monkeypatch, tmp_path):
    install_fake_akshare(monkeypatch, fail_symbols={"600000"})

    ingest_stock_daily(
        symbols=["000001", "600000"],
        start_date="20240101",
        end_date="20240131",
        output_path=tmp_path / "ods" / "stock_daily.parquet",
        report_path=tmp_path / "reports" / "ingestion_report.parquet",
        run_log_path=tmp_path / "reports" / "ingestion_runs.parquet",
        retry_wait_seconds=0,
    )

    run_log = pd.read_parquet(tmp_path / "reports" / "ingestion_runs.parquet")
    assert len(run_log) == 1
    assert run_log.loc[0, "symbols_count"] == 2
    assert run_log.loc[0, "success_count"] == 1
    assert run_log.loc[0, "failed_count"] == 1
    assert run_log.loc[0, "output_rows"] == 1
