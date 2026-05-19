import pandas as pd

from quant_data.evaluation.sensitivity import parse_float_list
from quant_data.evaluation.sensitivity import parse_int_list
from quant_data.evaluation.sensitivity import run_parameter_sensitivity


def test_parse_parameter_lists():
    assert parse_float_list("0.1,0.2, 0.3") == [0.1, 0.2, 0.3]
    assert parse_int_list("5,10, 20") == [5, 10, 20]


def test_run_parameter_sensitivity_outputs_grid_rows():
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

    result = run_parameter_sensitivity(
        factors,
        daily,
        "factor",
        factor_directions=["top", "bottom"],
        top_quantiles=[0.5, 1.0],
        rebalance_intervals=[1, 2],
        transaction_cost=0.0,
        commission_rate=0.0,
        slippage_rate=0.0,
        stamp_tax_rate=0.0,
    )

    assert len(result) == 8
    assert {
        "factor_name",
        "factor_direction",
        "top_quantile",
        "rebalance_interval",
        "sharpe",
        "turnover",
        "total_return",
        "index_excess_return",
    }.issubset(result.columns)
