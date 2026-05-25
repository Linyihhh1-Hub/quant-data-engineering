import pandas as pd

from quant_data.evaluation.validation import build_candidate_validation_reports
from quant_data.evaluation.validation import write_candidate_validation_reports


def make_validation_data(tmp_path):
    ads_dir = tmp_path / "ads"
    dwd_dir = tmp_path / "dwd"
    ads_dir.mkdir(parents=True)
    dwd_dir.mkdir(parents=True)

    symbols = ["AAA", "BBB", "CCC", "DDD"]
    rows = []
    factor_rows = []
    for day_index in range(12):
        trade_date = pd.Timestamp("2024-01-01") + pd.Timedelta(days=day_index)
        for symbol_index, symbol in enumerate(symbols):
            rows.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "close": 10.0 + day_index + symbol_index,
                    "amount": 1_000_000 + symbol_index,
                    "volume": 10_000 + symbol_index,
                    "is_suspended": False,
                    "is_limit_up": False,
                    "is_limit_down": False,
                }
            )
            factor_rows.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "test_factor": float(symbol_index),
                }
            )

    pd.DataFrame(rows).to_parquet(dwd_dir / "stock_daily.parquet", index=False)
    pd.DataFrame(factor_rows).to_parquet(ads_dir / "factor_wide_daily.parquet", index=False)
    pd.DataFrame(
        [
            {
                "rank": 1,
                "source": "backtest_metrics",
                "factor_name": "test_factor",
                "factor_direction": "top",
                "top_quantile": 0.5,
                "rebalance_interval": 1,
            }
        ]
    ).to_parquet(ads_dir / "strategy_optimization_report.parquet", index=False)


def test_build_candidate_validation_reports_splits_train_and_validation(tmp_path):
    make_validation_data(tmp_path)

    summary, yearly = build_candidate_validation_reports(
        tmp_path,
        top_n=1,
        validation_start="2024-01-07",
        transaction_cost=0.0,
    )

    assert summary.loc[0, "factor_name"] == "test_factor"
    assert summary.loc[0, "source_rank"] == 1
    assert summary.loc[0, "train_period_start"] == pd.Timestamp("2024-01-01")
    assert summary.loc[0, "validation_period_start"] == pd.Timestamp("2024-01-07")
    assert "validation_sharpe" in summary.columns
    assert "validation_status" in summary.columns
    assert yearly.loc[0, "year"] == 2024
    assert yearly.loc[0, "factor_name"] == "test_factor"


def test_write_candidate_validation_reports_writes_two_outputs(tmp_path):
    make_validation_data(tmp_path)

    summary_path, yearly_path = write_candidate_validation_reports(
        tmp_path,
        top_n=1,
        validation_start="2024-01-07",
        transaction_cost=0.0,
    )

    assert summary_path == tmp_path / "ads" / "candidate_validation_report.parquet"
    assert yearly_path == tmp_path / "ads" / "candidate_yearly_validation.parquet"
    assert pd.read_parquet(summary_path).loc[0, "factor_name"] == "test_factor"
    assert pd.read_parquet(yearly_path).loc[0, "factor_name"] == "test_factor"
