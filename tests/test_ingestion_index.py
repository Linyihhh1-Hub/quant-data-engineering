import sys
import types

import pandas as pd

from quant_data.ingestion.index import fetch_hs300_index
from quant_data.ingestion.index import write_hs300_index


def test_fetch_hs300_index_standardizes_and_filters_daily_endpoint(monkeypatch):
    fake = types.ModuleType("akshare")
    calls = []

    def stock_zh_index_daily(symbol: str):
        calls.append(symbol)
        return pd.DataFrame(
            [
                {"date": "2019-12-31", "open": 99.0, "high": 100.0, "low": 98.0, "close": 99.5, "volume": 1},
                {"date": "2020-01-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 2},
                {"date": "2020-01-03", "open": 101.0, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 3},
            ]
        )

    fake.stock_zh_index_daily = stock_zh_index_daily
    monkeypatch.setitem(sys.modules, "akshare", fake)

    result = fetch_hs300_index("20200101", "20200103")

    assert calls == ["sh000300"]
    assert result["symbol"].tolist() == ["000300.SH", "000300.SH"]
    assert result["trade_date"].min() == pd.Timestamp("2020-01-02")
    assert "amount" in result.columns


def test_fetch_hs300_index_falls_back_to_hist_endpoint(monkeypatch):
    fake = types.ModuleType("akshare")
    calls = []

    def index_zh_a_hist(symbol: str, period: str, start_date: str, end_date: str):
        calls.append((symbol, period, start_date, end_date))
        return pd.DataFrame(
            [
                {
                    "日期": "2020-01-02",
                    "开盘": 100.0,
                    "最高": 101.0,
                    "最低": 99.0,
                    "收盘": 100.5,
                    "成交量": 10,
                    "成交额": 1000,
                }
            ]
        )

    fake.index_zh_a_hist = index_zh_a_hist
    monkeypatch.setitem(sys.modules, "akshare", fake)

    result = fetch_hs300_index("20200101", "20200103")

    assert calls == [("000300", "daily", "20200101", "20200103")]
    assert result.loc[0, "close"] == 100.5


def test_write_hs300_index_writes_parquet(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "quant_data.ingestion.index.fetch_hs300_index",
        lambda start_date, end_date: pd.DataFrame(
            [{"trade_date": pd.Timestamp("2020-01-02"), "symbol": "000300.SH", "close": 100.5}]
        ),
    )

    output = write_hs300_index("20200101", "20200103", tmp_path / "dim" / "hs300_index.parquet")

    assert output.exists()
    assert pd.read_parquet(output).loc[0, "symbol"] == "000300.SH"
