import pandas as pd

from quant_data.quality.rules import run_quality_checks


def valid_quality_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"trade_date": "2024-01-02", "symbol": "000001.SZ", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2, "volume": 1000.0, "return_1d": 0.02},
            {"trade_date": "2024-01-02", "symbol": "600000.SH", "open": 8.0, "high": 8.2, "low": 7.9, "close": 8.1, "volume": 1200.0, "return_1d": 0.01},
            {"trade_date": "2024-01-03", "symbol": "000001.SZ", "open": 10.2, "high": 10.8, "low": 10.1, "close": 10.6, "volume": 1100.0, "return_1d": 0.039216},
            {"trade_date": "2024-01-03", "symbol": "600000.SH", "open": 8.1, "high": 8.5, "low": 8.0, "close": 8.4, "volume": 1300.0, "return_1d": 0.037037},
        ]
    )


def result_for(report: pd.DataFrame, rule_name: str) -> pd.Series:
    return report.loc[report["rule_name"] == rule_name].iloc[0]


def test_quality_checks_pass_for_valid_frame():
    report = run_quality_checks(valid_quality_frame(), min_rows_per_date=2)

    assert set(report["rule_name"]) == {
        "primary_key_unique",
        "required_fields_not_null",
        "price_valid",
        "volume_valid",
        "date_completeness",
        "abnormal_return",
    }
    assert report["status"].tolist() == ["PASS"] * 6
    assert report["failed_count"].tolist() == [0] * 6


def test_quality_checks_detect_duplicate_primary_key():
    frame = pd.concat([valid_quality_frame(), valid_quality_frame().iloc[[0]]], ignore_index=True)

    report = run_quality_checks(frame, min_rows_per_date=2)
    result = result_for(report, "primary_key_unique")

    assert result["status"] == "FAIL"
    assert result["failed_count"] == 2
    assert "000001.SZ" in result["failed_sample"]


def test_quality_checks_detect_null_required_fields():
    frame = valid_quality_frame()
    frame.loc[0, "close"] = None

    report = run_quality_checks(frame, min_rows_per_date=2)
    result = result_for(report, "required_fields_not_null")

    assert result["status"] == "FAIL"
    assert result["failed_count"] == 1
    assert "close" in result["failed_sample"]


def test_quality_checks_detect_invalid_prices():
    frame = valid_quality_frame()
    frame.loc[0, "high"] = 9.0
    frame.loc[1, "close"] = 0.0

    report = run_quality_checks(frame, min_rows_per_date=2)
    result = result_for(report, "price_valid")

    assert result["status"] == "FAIL"
    assert result["failed_count"] == 2


def test_quality_checks_detect_invalid_volume():
    frame = valid_quality_frame()
    frame.loc[0, "volume"] = -1.0

    report = run_quality_checks(frame, min_rows_per_date=2)
    result = result_for(report, "volume_valid")

    assert result["status"] == "FAIL"
    assert result["failed_count"] == 1


def test_quality_checks_detect_incomplete_dates():
    frame = valid_quality_frame()
    frame = frame[~((frame["trade_date"] == "2024-01-03") & (frame["symbol"] == "600000.SH"))]

    report = run_quality_checks(frame, min_rows_per_date=2)
    result = result_for(report, "date_completeness")

    assert result["status"] == "FAIL"
    assert result["failed_count"] == 1
    assert "2024-01-03" in result["failed_sample"]


def test_quality_checks_detect_abnormal_return():
    frame = valid_quality_frame()
    frame.loc[0, "return_1d"] = 0.35

    report = run_quality_checks(frame, min_rows_per_date=2, abnormal_return_threshold=0.2)
    result = result_for(report, "abnormal_return")

    assert result["status"] == "FAIL"
    assert result["failed_count"] == 1
    assert "0.35" in result["failed_sample"]
