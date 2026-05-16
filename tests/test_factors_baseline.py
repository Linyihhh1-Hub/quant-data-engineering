import pandas as pd

from quant_data.factors.baseline import FACTOR_COLUMNS, compute_baseline_factors


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

    assert result.columns.tolist() == ["trade_date", "symbol", *FACTOR_COLUMNS]
    assert result[["symbol", "trade_date"]].equals(
        result[["symbol", "trade_date"]].sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    )


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
