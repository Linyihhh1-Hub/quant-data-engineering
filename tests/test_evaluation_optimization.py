import json

import pandas as pd

from quant_data.evaluation.optimization import build_strategy_optimization_report
from quant_data.evaluation.optimization import write_strategy_optimization_report


def test_build_strategy_optimization_report_ranks_candidates_and_flags_cost_drag(tmp_path):
    ads_dir = tmp_path / "ads"
    ads_dir.mkdir(parents=True)
    (ads_dir / "backtest_metrics_momentum_20d_zscore.json").write_text(
        json.dumps(
            {
                "total_return": 0.12,
                "annualized_return": 0.03,
                "sharpe": 0.2,
                "max_drawdown": -0.34,
                "turnover": 85.0,
                "total_cost": 0.17,
                "cost_drag": 0.21,
                "cost_to_return": 0.5,
                "factor_direction": "top",
                "top_quantile": 0.1,
                "rebalance_interval": 20,
            }
        ),
        encoding="utf-8",
    )
    (ads_dir / "backtest_metrics_volatility_20d.json").write_text(
        json.dumps(
            {
                "total_return": 0.71,
                "annualized_return": 0.12,
                "sharpe": 1.03,
                "max_drawdown": -0.12,
                "turnover": 50.0,
                "total_cost": 0.10,
                "cost_drag": 0.08,
                "cost_to_return": 0.12,
                "factor_direction": "bottom",
                "top_quantile": 0.1,
                "rebalance_interval": 20,
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "factor_name": "momentum_20d_zscore",
                "factor_direction": "bottom",
                "top_quantile": 0.2,
                "rebalance_interval": 40,
                "annualized_return": 0.16,
                "total_return": 1.1,
                "sharpe": 0.76,
                "max_drawdown": -0.26,
                "turnover": 48.0,
                "total_cost": 0.09,
                "cost_drag": 0.12,
                "cost_to_return": 0.07,
                "average_exposure": 1.0,
            }
        ]
    ).to_parquet(ads_dir / "parameter_sensitivity.parquet", index=False)

    report = build_strategy_optimization_report(tmp_path)

    assert report.iloc[0]["factor_name"] == "volatility_20d"
    assert report.iloc[0]["recommendation"] == "prefer"
    high_cost = report.loc[
        (report["factor_name"] == "momentum_20d_zscore") & (report["source"] == "backtest_metrics")
    ].iloc[0]
    assert high_cost["cost_warning"] == "high_cost_drag"
    assert "increase rebalance interval" in high_cost["suggested_action"]
    assert {"source", "score", "rank", "risk_warning", "suggested_action"}.issubset(report.columns)


def test_write_strategy_optimization_report_writes_parquet(tmp_path):
    ads_dir = tmp_path / "ads"
    ads_dir.mkdir(parents=True)
    (ads_dir / "backtest_metrics_factor.json").write_text(
        json.dumps(
            {
                "total_return": 0.2,
                "annualized_return": 0.05,
                "sharpe": 0.6,
                "max_drawdown": -0.2,
                "turnover": 20.0,
                "cost_drag": 0.03,
                "cost_to_return": 0.1,
            }
        ),
        encoding="utf-8",
    )

    output_path = write_strategy_optimization_report(tmp_path)

    assert output_path == tmp_path / "ads" / "strategy_optimization_report.parquet"
    written = pd.read_parquet(output_path)
    assert written.loc[0, "factor_name"] == "factor"
