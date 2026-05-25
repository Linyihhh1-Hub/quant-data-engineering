import pandas as pd

from quant_data.factors.baseline import ALL_FACTOR_COLUMNS, COMPOSITE_FACTOR_COLUMNS, FACTOR_COLUMNS, ZSCORE_FACTOR_COLUMNS, compute_baseline_factors


def make_factor_frame() -> pd.DataFrame:
    rows = []
    for idx in range(25):
        day = pd.Timestamp("2024-01-01") + pd.Timedelta(days=idx)
        rows.append(
            {
                "trade_date": day,
                "symbol": "000001.SZ",
                "close": float(idx + 1),
                "volume": float((idx + 1) * 10),
                "return_1d": None if idx == 0 else 1 / idx,
            }
        )
        rows.append(
            {
                "trade_date": day,
                "symbol": "600000.SH",
                "close": float((idx + 1) * 2),
                "volume": float((idx + 1) * 20),
                "return_1d": None if idx == 0 else 1 / idx,
            }
        )
    return pd.DataFrame(rows).sample(frac=1, random_state=42).reset_index(drop=True)


def test_compute_baseline_factors_returns_expected_columns_and_sorting():
    result = compute_baseline_factors(make_factor_frame())

    assert result.columns.tolist() == ["trade_date", "symbol", *ALL_FACTOR_COLUMNS]
    assert result[["symbol", "trade_date"]].equals(
        result[["symbol", "trade_date"]].sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    )
    for column in ZSCORE_FACTOR_COLUMNS:
        assert column in result.columns
    for column in COMPOSITE_FACTOR_COLUMNS:
        assert column in result.columns


def test_compute_baseline_factors_calculates_twenty_day_momentum_per_symbol():
    result = compute_baseline_factors(make_factor_frame())
    pingan = result[result["symbol"] == "000001.SZ"].reset_index(drop=True)

    assert pd.isna(pingan.loc[19, "momentum_20d"])
    assert round(pingan.loc[20, "momentum_20d"], 6) == 20.0


def test_compute_baseline_factors_calculates_five_day_reversal():
    result = compute_baseline_factors(make_factor_frame())
    pingan = result[result["symbol"] == "000001.SZ"].reset_index(drop=True)

    expected = -1 * (6.0 / 1.0 - 1)
    assert round(pingan.loc[5, "reversal_5d"], 6) == expected


def test_compute_baseline_factors_calculates_volume_ratio():
    result = compute_baseline_factors(make_factor_frame())
    pingan = result[result["symbol"] == "000001.SZ"].reset_index(drop=True)

    expected = 50.0 / 30.0
    assert round(pingan.loc[4, "volume_ratio_5d"], 6) == round(expected, 6)


def test_compute_baseline_factors_calculates_ma_bias():
    result = compute_baseline_factors(make_factor_frame())
    pingan = result[result["symbol"] == "000001.SZ"].reset_index(drop=True)

    expected = 20.0 / 10.5 - 1
    assert round(pingan.loc[19, "ma_bias_20d"], 6) == round(expected, 6)


def test_compute_baseline_factors_does_not_leak_across_symbols():
    result = compute_baseline_factors(make_factor_frame())
    pudong = result[result["symbol"] == "600000.SH"].reset_index(drop=True)

    assert pd.isna(pudong.loc[19, "momentum_20d"])
    assert round(pudong.loc[20, "momentum_20d"], 6) == 20.0


def test_compute_baseline_factors_adds_low_volatility_ma_bias_composite():
    result = compute_baseline_factors(make_factor_frame())
    valid = result.dropna(subset=["volatility_20d_zscore", "ma_bias_20d_zscore", "low_volatility_ma_bias_score"])

    expected = (valid["volatility_20d_zscore"] + valid["ma_bias_20d_zscore"]) / 2
    pd.testing.assert_series_equal(
        valid["low_volatility_ma_bias_score"].reset_index(drop=True),
        expected.reset_index(drop=True),
        check_names=False,
    )


def test_compute_baseline_factors_calculates_relative_strength_against_daily_universe():
    result = compute_baseline_factors(make_relative_strength_frame())
    latest = result[result["trade_date"] == pd.Timestamp("2024-03-01")].sort_values("symbol").reset_index(drop=True)
    expected_20d = ((220.0 / 180.0 - 1) - (160.0 / 140.0 - 1)) / 2

    assert round(latest.loc[0, "relative_strength_20d"], 6) == round(expected_20d, 6)
    assert round(latest.loc[1, "relative_strength_20d"], 6) == round(-expected_20d, 6)
    assert round(latest.loc[0, "relative_strength_60d"], 6) == 0.3
    assert round(latest.loc[1, "relative_strength_60d"], 6) == -0.3


def test_compute_baseline_factors_adds_relative_strength_composite():
    result = compute_baseline_factors(make_relative_strength_frame())
    valid = result.dropna(
        subset=[
            "volatility_20d_zscore",
            "ma_bias_20d_zscore",
            "relative_strength_20d_zscore",
            "relative_strength_60d_zscore",
            "low_volatility_ma_bias_relative_strength_score",
        ]
    )

    expected = (
        valid["volatility_20d_zscore"]
        + valid["ma_bias_20d_zscore"]
        - valid["relative_strength_20d_zscore"]
        - valid["relative_strength_60d_zscore"]
    ) / 4
    pd.testing.assert_series_equal(
        valid["low_volatility_ma_bias_relative_strength_score"].reset_index(drop=True),
        expected.reset_index(drop=True),
        check_names=False,
    )


def make_relative_strength_frame() -> pd.DataFrame:
    rows = []
    for idx in range(61):
        day = pd.Timestamp("2024-01-01") + pd.Timedelta(days=idx)
        slow_close = 100.0 + idx
        strong_close = 100.0 + idx * 2
        rows.append(
            {
                "trade_date": day,
                "symbol": "000001.SZ",
                "close": strong_close,
                "volume": 1000.0 + idx,
                "return_1d": None if idx == 0 else strong_close / (100.0 + (idx - 1) * 2) - 1,
            }
        )
        rows.append(
            {
                "trade_date": day,
                "symbol": "600000.SH",
                "close": slow_close,
                "volume": 1000.0 + idx,
                "return_1d": None if idx == 0 else slow_close / (100.0 + idx - 1) - 1,
            }
        )
    return pd.DataFrame(rows)
