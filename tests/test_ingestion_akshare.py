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
