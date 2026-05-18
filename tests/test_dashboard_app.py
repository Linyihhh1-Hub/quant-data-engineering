import json

import pandas as pd

from quant_data.dashboard.app import (
    build_backtest_summary,
    build_factor_summary,
    build_pipeline_summary,
    list_available_factors,
)


def write_dashboard_fixture(root):
    (root / "ods").mkdir()
    (root / "dwd").mkdir()
    (root / "ads").mkdir()
    (root / "reports").mkdir()

    ods = pd.DataFrame(
        [
            {"trade_date": "2024-01-01", "symbol": "000001.SZ"},
            {"trade_date": "2024-01-02", "symbol": "000001.SZ"},
            {"trade_date": "2024-01-02", "symbol": "600000.SH"},
        ]
    )
    dwd = pd.DataFrame(
        [
            {"trade_date": pd.Timestamp("2024-01-01"), "symbol": "000001.SZ"},
            {"trade_date": pd.Timestamp("2024-01-02"), "symbol": "000001.SZ"},
        ]
    )
    factors = pd.DataFrame(
        [
            {"trade_date": pd.Timestamp("2024-01-01"), "symbol": "000001.SZ", "momentum_20d": 0.1},
            {"trade_date": pd.Timestamp("2024-01-02"), "symbol": "000001.SZ", "momentum_20d": 0.2},
        ]
    )
    ingestion_report = pd.DataFrame(
        [
            {"symbol": "000001.SZ", "status": "SUCCESS", "row_count": 2, "message": ""},
            {"symbol": "600000.SH", "status": "FAILED", "row_count": 0, "message": "timeout"},
        ]
    )
    quality_report = pd.DataFrame(
        [
            {"rule_name": "primary_key_unique", "status": "PASS", "failed_count": 0, "failed_sample": ""},
            {"rule_name": "min_rows_per_date", "status": "FAIL", "failed_count": 1, "failed_sample": "2024-01-01"},
        ]
    )
    evaluation = pd.DataFrame(
        [
            {
                "trade_date": pd.Timestamp("2024-01-01"),
                "factor_name": "momentum_20d",
                "ic": 0.1,
                "rank_ic": 0.2,
                "top_group_return": 0.03,
                "bottom_group_return": 0.01,
                "long_short_return": 0.02,
            },
            {
                "trade_date": pd.Timestamp("2024-01-02"),
                "factor_name": "momentum_20d",
                "ic": -0.05,
                "rank_ic": 0.0,
                "top_group_return": 0.02,
                "bottom_group_return": 0.03,
                "long_short_return": -0.01,
            },
        ]
    )
    backtest = pd.DataFrame(
        [
            {
                "trade_date": pd.Timestamp("2024-01-01"),
                "portfolio_value": 1.0,
                "benchmark_value": 1.0,
                "drawdown": 0.0,
                "target_exposure": 1.0,
            },
            {
                "trade_date": pd.Timestamp("2024-01-02"),
                "portfolio_value": 1.1,
                "benchmark_value": 1.05,
                "drawdown": -0.03,
                "target_exposure": 0.3,
            },
        ]
    )
    metrics = {
        "total_return": 0.1,
        "annualized_return": 0.2,
        "max_drawdown": -0.03,
        "sharpe": 1.5,
        "turnover": 2.0,
        "average_exposure": 0.65,
    }

    ods.to_parquet(root / "ods" / "stock_daily.parquet", index=False)
    dwd.to_parquet(root / "dwd" / "stock_daily.parquet", index=False)
    factors.to_parquet(root / "ads" / "factor_wide_daily.parquet", index=False)
    ingestion_report.to_parquet(root / "reports" / "ingestion_report.parquet", index=False)
    quality_report.to_parquet(root / "reports" / "data_quality_report.parquet", index=False)
    evaluation.to_parquet(root / "ads" / "factor_eval_momentum_20d.parquet", index=False)
    backtest.to_parquet(root / "ads" / "backtest_daily_momentum_20d.parquet", index=False)
    (root / "ads" / "backtest_metrics_momentum_20d.json").write_text(
        json.dumps(metrics),
        encoding="utf-8",
    )


def test_build_pipeline_summary_returns_core_counts_and_exceptions(tmp_path):
    write_dashboard_fixture(tmp_path)

    summary = build_pipeline_summary(tmp_path)

    assert summary["ods_rows"] == 3
    assert summary["dwd_rows"] == 2
    assert summary["factor_rows"] == 2
    assert summary["symbol_count"] == 2
    assert summary["date_range"] == "2024-01-01 ~ 2024-01-02"
    assert summary["quality_pass_count"] == 1
    assert summary["quality_fail_count"] == 1
    assert summary["failed_symbols"]["symbol"].tolist() == ["600000.SH"]
    assert summary["failed_quality_rules"]["rule_name"].tolist() == ["min_rows_per_date"]


def test_build_factor_summary_returns_ic_metrics(tmp_path):
    write_dashboard_fixture(tmp_path)

    summary = build_factor_summary(tmp_path, "momentum_20d")

    assert round(summary["ic_mean"], 6) == 0.025
    assert round(summary["rank_ic_mean"], 6) == 0.1
    assert summary["positive_ic_ratio"] == 0.5
    assert "icir" in summary
    assert len(summary["evaluation"]) == 2


def test_build_backtest_summary_reads_daily_result_and_metrics(tmp_path):
    write_dashboard_fixture(tmp_path)

    summary = build_backtest_summary(tmp_path, "momentum_20d")

    assert summary["metrics"]["total_return"] == 0.1
    assert summary["metrics"]["average_exposure"] == 0.65
    assert summary["daily"]["target_exposure"].tolist() == [1.0, 0.3]


def test_list_available_factors_uses_factor_eval_files(tmp_path):
    write_dashboard_fixture(tmp_path)

    assert list_available_factors(tmp_path) == ["momentum_20d"]
