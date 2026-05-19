import pandas as pd
import pytest

from quant_data.factors.preprocessing import add_standardized_factors
from quant_data.factors.preprocessing import winsorize_cross_section
from quant_data.factors.preprocessing import zscore_cross_section


def make_cross_section_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"trade_date": "2024-01-02", "symbol": "000001.SZ", "factor": 1.0},
            {"trade_date": "2024-01-02", "symbol": "000002.SZ", "factor": 2.0},
            {"trade_date": "2024-01-02", "symbol": "600000.SH", "factor": 3.0},
            {"trade_date": "2024-01-02", "symbol": "600001.SH", "factor": 100.0},
            {"trade_date": "2024-01-03", "symbol": "000001.SZ", "factor": 5.0},
            {"trade_date": "2024-01-03", "symbol": "000002.SZ", "factor": 5.0},
        ]
    )


def test_winsorize_cross_section_clips_by_trade_date():
    result = winsorize_cross_section(make_cross_section_frame(), ["factor"], lower_quantile=0.25, upper_quantile=0.75)
    day = result[result["trade_date"] == pd.Timestamp("2024-01-02")]

    assert day["factor_winsorized"].min() >= 1.75
    assert day["factor_winsorized"].max() <= 27.25


def test_zscore_cross_section_standardizes_each_trade_date():
    result = zscore_cross_section(make_cross_section_frame(), ["factor"])
    day = result[result["trade_date"] == pd.Timestamp("2024-01-02")]
    constant_day = result[result["trade_date"] == pd.Timestamp("2024-01-03")]

    assert round(day["factor_zscore"].mean(), 6) == 0.0
    assert constant_day["factor_zscore"].tolist() == [0.0, 0.0]


def test_add_standardized_factors_adds_winsorized_and_zscore_columns():
    result = add_standardized_factors(make_cross_section_frame(), ["factor"], lower_quantile=0.25, upper_quantile=0.75)

    assert "factor_winsorized" in result.columns
    assert "factor_zscore" in result.columns


def test_winsorize_cross_section_rejects_invalid_quantiles():
    with pytest.raises(ValueError, match="lower_quantile"):
        winsorize_cross_section(make_cross_section_frame(), ["factor"], lower_quantile=0.8, upper_quantile=0.2)
