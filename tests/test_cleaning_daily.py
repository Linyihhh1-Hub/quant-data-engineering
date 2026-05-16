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
