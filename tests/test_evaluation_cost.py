import pandas as pd

from quant_data.evaluation.cost import run_cost_sensitivity


def test_run_cost_sensitivity_shows_cost_drag():
    daily = pd.DataFrame(
        [
            {"trade_date": "2024-01-01", "symbol": "000001.SZ", "close": 10.0},
            {"trade_date": "2024-01-02", "symbol": "000001.SZ", "close": 11.0},
            {"trade_date": "2024-01-03", "symbol": "000001.SZ", "close": 12.0},
            {"trade_date": "2024-01-01", "symbol": "600000.SH", "close": 20.0},
            {"trade_date": "2024-01-02", "symbol": "600000.SH", "close": 19.0},
            {"trade_date": "2024-01-03", "symbol": "600000.SH", "close": 18.0},
        ]
    )
    factors = pd.DataFrame(
        [
            {"trade_date": "2024-01-01", "symbol": "000001.SZ", "factor": 1.0},
            {"trade_date": "2024-01-01", "symbol": "600000.SH", "factor": 0.1},
        ]
    )

    result = run_cost_sensitivity(
        factors,
        daily,
        "factor",
        factor_direction="top",
        top_quantile=0.5,
        rebalance_interval=1,
    )

    no_cost = result[result["cost_scenario"] == "no_cost"].iloc[0]
    default_cost = result[result["cost_scenario"] == "default_cost"].iloc[0]
    assert no_cost["total_return"] >= default_cost["total_return"]
    assert default_cost["cost_drag"] > 0
