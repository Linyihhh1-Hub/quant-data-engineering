import json

import pandas as pd

from quant_data.cli import main


def make_pipeline_raw_frame() -> pd.DataFrame:
    rows = []
    for idx in range(25):
        day = pd.Timestamp("2024-01-01") + pd.Timedelta(days=idx)
        rows.extend(
            [
                {"trade_date": day, "symbol": "000001", "open": 10 + idx, "high": 10.5 + idx, "low": 9.5 + idx, "close": 10 + idx, "volume": 1000 + idx, "amount": 10000 + idx},
                {"trade_date": day, "symbol": "000002", "open": 20 + idx, "high": 20.5 + idx, "low": 19.5 + idx, "close": 20 + idx, "volume": 2000 + idx, "amount": 20000 + idx},
                {"trade_date": day, "symbol": "600000", "open": 30 + idx, "high": 30.5 + idx, "low": 29.5 + idx, "close": 30 + idx, "volume": 3000 + idx, "amount": 30000 + idx},
                {"trade_date": day, "symbol": "600001", "open": 40 + idx, "high": 40.5 + idx, "low": 39.5 + idx, "close": 40 + idx, "volume": 4000 + idx, "amount": 40000 + idx},
            ]
        )
    return pd.DataFrame(rows)


def test_cli_run_all_writes_pipeline_outputs(tmp_path):
    raw_path = tmp_path / "ods" / "stock_daily.parquet"
    raw_path.parent.mkdir(parents=True)
    make_pipeline_raw_frame().to_parquet(raw_path, index=False)

    exit_code = main(
        [
            "run-all",
            "--input",
            str(raw_path),
            "--output-dir",
            str(tmp_path),
            "--factor-name",
            "momentum_20d",
            "--horizon",
            "1",
            "--groups",
            "2",
            "--top-quantile",
            "0.5",
            "--rebalance-interval",
            "5",
            "--min-rows-per-date",
            "4",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "dwd" / "stock_daily.parquet").exists()
    assert (tmp_path / "reports" / "data_quality_report.parquet").exists()
    assert (tmp_path / "ads" / "factor_wide_daily.parquet").exists()
    assert (tmp_path / "ads" / "factor_eval_momentum_20d.parquet").exists()
    assert (tmp_path / "ads" / "backtest_daily_momentum_20d.parquet").exists()

    metrics_path = tmp_path / "ads" / "backtest_metrics_momentum_20d.json"
    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert {"total_return", "annualized_return", "max_drawdown", "sharpe", "turnover"} == set(metrics)
