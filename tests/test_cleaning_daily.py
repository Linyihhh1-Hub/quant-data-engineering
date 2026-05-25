import pandas as pd

from quant_data.cleaning.daily import clean_daily_bars


def test_clean_daily_bars_normalizes_types_and_symbols(raw_daily_frame):
    result = clean_daily_bars(raw_daily_frame)

    assert str(result["trade_date"].dtype) == "datetime64[ns]"
    assert result.loc[result["symbol"].str.startswith("000001"), "symbol"].iloc[0] == "000001.SZ"
    assert result.loc[result["symbol"].str.startswith("600000"), "symbol"].iloc[0] == "600000.SH"
    assert pd.api.types.is_float_dtype(result["close"])


def test_clean_daily_bars_sorts_and_deduplicates(raw_daily_frame):
    result = clean_daily_bars(raw_daily_frame)

    assert len(result) == 4
    assert result[["trade_date", "symbol"]].duplicated().sum() == 0
    assert result[["symbol", "trade_date"]].equals(result[["symbol", "trade_date"]].sort_values(["symbol", "trade_date"]).reset_index(drop=True))


def test_clean_daily_bars_computes_return_per_symbol(raw_daily_frame):
    result = clean_daily_bars(raw_daily_frame)
    pingan = result[result["symbol"] == "000001.SZ"].reset_index(drop=True)

    assert pd.isna(pingan.loc[0, "return_1d"])
    assert round(pingan.loc[1, "return_1d"], 6) == 0.05


def test_clean_daily_bars_adds_trading_constraint_flags():
    frame = pd.DataFrame(
        [
            {"trade_date": "2024-01-01", "symbol": "000001", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 100, "amount": 1000},
            {"trade_date": "2024-01-02", "symbol": "000001", "open": 11, "high": 11, "low": 11, "close": 11, "volume": 100, "amount": 1100},
            {"trade_date": "2024-01-03", "symbol": "000001", "open": 9.9, "high": 9.9, "low": 9.9, "close": 9.9, "volume": 0, "amount": 0},
        ]
    )

    result = clean_daily_bars(frame).reset_index(drop=True)

    assert result.loc[1, "is_limit_up"] == True
    assert result.loc[2, "is_limit_down"] == True
    assert result.loc[2, "is_suspended"] == True


def test_clean_daily_bars_merges_stock_basic_flags():
    frame = pd.DataFrame(
        [
            {"trade_date": "2024-01-01", "symbol": "000001", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 100, "amount": 1000},
            {"trade_date": "2024-01-01", "symbol": "600000", "open": 20, "high": 20, "low": 20, "close": 20, "volume": 100, "amount": 2000},
        ]
    )
    stock_basic = pd.DataFrame(
        [
            {"symbol": "000001.SZ", "name": "平安银行", "exchange": "SZ", "is_st": False},
            {"symbol": "600000.SH", "name": "ST浦发", "exchange": "SH", "is_st": True},
        ]
    )

    result = clean_daily_bars(frame, stock_basic=stock_basic)

    pingan = result[result["symbol"] == "000001.SZ"].iloc[0]
    st_stock = result[result["symbol"] == "600000.SH"].iloc[0]
    assert pingan["is_st"] == False
    assert pingan["exchange"] == "SZ"
    assert pingan["name"] == "平安银行"
    assert st_stock["is_st"] == True
