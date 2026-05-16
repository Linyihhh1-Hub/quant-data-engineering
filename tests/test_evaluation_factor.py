import pandas as pd

from quant_data.evaluation.factor import (
    add_forward_return,
    compute_group_return_report,
    compute_ic_report,
    evaluate_factor,
)


def make_daily_bars() -> pd.DataFrame:
    rows = []
    for idx in range(5):
        day = pd.Timestamp("2024-01-01") + pd.Timedelta(days=idx)
        rows.extend(
            [
                {"trade_date": day, "symbol": "000001.SZ", "close": float(10 + idx)},
                {"trade_date": day, "symbol": "000002.SZ", "close": float(20 + idx * 2)},
                {"trade_date": day, "symbol": "600000.SH", "close": float(30 - idx)},
                {"trade_date": day, "symbol": "600001.SH", "close": float(40 - idx * 2)},
            ]
        )
    return pd.DataFrame(rows).sample(frac=1, random_state=7).reset_index(drop=True)


def make_factor_frame() -> pd.DataFrame:
    rows = []
    values_by_date = {
        0: [1.0, 2.0, 3.0, 4.0],
        1: [4.0, 3.0, 2.0, 1.0],
        2: [1.0, 1.0, 1.0, 1.0],
    }
    symbols = ["000001.SZ", "000002.SZ", "600000.SH", "600001.SH"]
    for idx, values in values_by_date.items():
        day = pd.Timestamp("2024-01-01") + pd.Timedelta(days=idx)
        for symbol, value in zip(symbols, values, strict=True):
            rows.append({"trade_date": day, "symbol": symbol, "test_factor": value})
    return pd.DataFrame(rows)


def test_add_forward_return_computes_per_symbol_without_leakage():
    result = add_forward_return(make_daily_bars(), horizon=1)
    pingan = result[result["symbol"] == "000001.SZ"].reset_index(drop=True)
    pudong = result[result["symbol"] == "600000.SH"].reset_index(drop=True)

    assert round(pingan.loc[0, "forward_return"], 6) == 0.1
    assert round(pudong.loc[0, "forward_return"], 6) == round(29 / 30 - 1, 6)
    assert pd.isna(pingan.loc[4, "forward_return"])


def test_compute_ic_report_calculates_ic_and_rank_ic_by_date():
    report = compute_ic_report(make_factor_frame(), make_daily_bars(), "test_factor", horizon=1)
    first_day = report[report["trade_date"] == pd.Timestamp("2024-01-01")].iloc[0]

    assert first_day["factor_name"] == "test_factor"
    assert round(first_day["ic"], 6) == -0.917564
    assert round(first_day["rank_ic"], 6) == -0.948683


def test_compute_group_return_report_calculates_top_bottom_and_long_short():
    report = compute_group_return_report(
        make_factor_frame(), make_daily_bars(), "test_factor", horizon=1, groups=2
    )
    first_day = report[report["trade_date"] == pd.Timestamp("2024-01-01")].iloc[0]

    bottom_expected = ((11 / 10 - 1) + (22 / 20 - 1)) / 2
    top_expected = ((29 / 30 - 1) + (38 / 40 - 1)) / 2

    assert round(first_day["bottom_group_return"], 6) == round(bottom_expected, 6)
    assert round(first_day["top_group_return"], 6) == round(top_expected, 6)
    assert round(first_day["long_short_return"], 6) == round(top_expected - bottom_expected, 6)


def test_evaluate_factor_merges_ic_and_group_reports():
    report = evaluate_factor(make_factor_frame(), make_daily_bars(), "test_factor", horizon=1, groups=2)

    assert report.columns.tolist() == [
        "trade_date",
        "factor_name",
        "ic",
        "rank_ic",
        "top_group_return",
        "bottom_group_return",
        "long_short_return",
    ]
    assert pd.Timestamp("2024-01-01") in set(report["trade_date"])
