import sys
import types

import pandas as pd

from quant_data.dimensions.market import (
    build_hs300_symbol_pool,
    build_stock_basic,
    build_trade_calendar,
)


def install_fake_akshare(monkeypatch):
    fake = types.ModuleType("akshare")

    def tool_trade_date_hist_sina():
        return pd.DataFrame({"trade_date": ["2024-01-01", "2024-01-02"]})

    def stock_info_a_code_name():
        return pd.DataFrame(
            {
                "code": ["000001", "000002", "600000"],
                "name": ["平安银行", "*ST万科", "浦发银行"],
            }
        )

    def stock_zh_a_st_em():
        return pd.DataFrame({"代码": ["000002"], "名称": ["ST万科"]})

    def index_stock_cons(symbol: str):
        assert symbol == "000300"
        return pd.DataFrame(
            {
                "品种代码": ["000001", "000002", "600000"],
                "品种名称": ["平安银行", "万科A", "浦发银行"],
            }
        )

    fake.tool_trade_date_hist_sina = tool_trade_date_hist_sina
    fake.stock_info_a_code_name = stock_info_a_code_name
    fake.stock_zh_a_st_em = stock_zh_a_st_em
    fake.index_stock_cons = index_stock_cons
    monkeypatch.setitem(sys.modules, "akshare", fake)


def test_build_trade_calendar_standardizes_dates(monkeypatch):
    install_fake_akshare(monkeypatch)

    result = build_trade_calendar("20240101", "20240102")

    assert result.columns.tolist() == ["trade_date", "is_open", "pre_trade_date", "next_trade_date"]
    assert result["is_open"].tolist() == [True, True]
    assert pd.isna(result.loc[0, "pre_trade_date"])
    assert result.loc[0, "next_trade_date"] == pd.Timestamp("2024-01-02")


def test_build_stock_basic_marks_st_symbols(monkeypatch):
    install_fake_akshare(monkeypatch)

    result = build_stock_basic()

    assert result.columns.tolist() == ["symbol", "raw_symbol", "name", "exchange", "is_st"]
    assert result[result["raw_symbol"] == "000002"]["is_st"].iloc[0] == True
    assert result[result["raw_symbol"] == "000001"]["exchange"].iloc[0] == "SZ"


def test_build_hs300_symbol_pool_filters_st(monkeypatch):
    install_fake_akshare(monkeypatch)

    result = build_hs300_symbol_pool(filter_st=True)

    assert result["symbol"].tolist() == ["000001", "600000"]
    assert result["name"].tolist() == ["平安银行", "浦发银行"]
