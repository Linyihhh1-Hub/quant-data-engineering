import pandas as pd

from quant_data.storage.clickhouse import load_pipeline_outputs, write_dataframe


class FakeClient:
    def __init__(self):
        self.commands = []
        self.inserts = []

    def command(self, sql: str):
        self.commands.append(sql)

    def insert_df(self, table: str, df: pd.DataFrame):
        self.inserts.append((table, df.copy()))


def write_required_outputs(tmp_path):
    dwd = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "symbol": ["000001.SZ"]})
    factors = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "symbol": ["000001.SZ"], "momentum_20d": [0.1]})
    sentiment = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "market_sentiment_score": [0.5]})
    eval_report = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "factor_name": ["momentum_20d"], "ic": [0.5]})
    backtest = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "portfolio_value": [1.0]})

    (tmp_path / "dwd").mkdir()
    (tmp_path / "ads").mkdir()
    dwd.to_parquet(tmp_path / "dwd" / "stock_daily.parquet", index=False)
    factors.to_parquet(tmp_path / "ads" / "factor_wide_daily.parquet", index=False)
    sentiment.to_parquet(tmp_path / "ads" / "market_sentiment_daily.parquet", index=False)
    eval_report.to_parquet(tmp_path / "ads" / "factor_eval_momentum_20d.parquet", index=False)
    backtest.to_parquet(tmp_path / "ads" / "backtest_daily_momentum_20d.parquet", index=False)


def test_write_dataframe_creates_table_and_inserts_rows():
    client = FakeClient()
    frame = pd.DataFrame(
        {
            "trade_date": [pd.Timestamp("2024-01-02")],
            "symbol": ["000001.SZ"],
            "close": [10.2],
            "volume": [1000],
        }
    )

    write_dataframe(client, "dwd_stock_daily", frame)

    assert client.commands[0] == "DROP TABLE IF EXISTS dwd_stock_daily"
    assert "CREATE TABLE dwd_stock_daily" in client.commands[1]
    assert "`trade_date` DateTime" in client.commands[1]
    assert "`symbol` String" in client.commands[1]
    assert "`close` Float64" in client.commands[1]
    assert "`volume` Int64" in client.commands[1]
    assert client.inserts[0][0] == "dwd_stock_daily"


def test_write_dataframe_uses_nullable_type_for_missing_datetime():
    client = FakeClient()
    frame = pd.DataFrame(
        {
            "trade_date": [pd.Timestamp("2024-01-02")],
            "pre_trade_date": [pd.NaT],
        }
    )

    write_dataframe(client, "dim_trade_calendar", frame)

    assert "`pre_trade_date` Nullable(DateTime)" in client.commands[1]


def test_load_pipeline_outputs_loads_expected_tables(tmp_path):
    client = FakeClient()
    write_required_outputs(tmp_path)

    loaded = load_pipeline_outputs(client, tmp_path, factor_name="momentum_20d")

    assert loaded == {
        "dwd_stock_daily": 1,
        "ads_factor_wide_daily": 1,
        "ads_market_sentiment_daily": 1,
        "ads_factor_eval": 1,
        "ads_backtest_daily": 1,
    }
    assert [table for table, _ in client.inserts] == [
        "dwd_stock_daily",
        "ads_factor_wide_daily",
        "ads_market_sentiment_daily",
        "ads_factor_eval",
        "ads_backtest_daily",
    ]


def test_load_pipeline_outputs_loads_ops_tables_when_reports_exist(tmp_path):
    client = FakeClient()
    write_required_outputs(tmp_path)
    ingestion_report = pd.DataFrame({"symbol": ["000001"], "status": ["SUCCESS"], "row_count": [1], "message": [""]})
    ingestion_runs = pd.DataFrame(
        {
            "run_id": ["run-1"],
            "started_at": [pd.Timestamp("2026-05-18", tz="UTC")],
            "ended_at": [pd.Timestamp("2026-05-18 00:01:00", tz="UTC")],
            "symbols_count": [1],
            "success_count": [1],
        }
    )
    quality = pd.DataFrame({"rule_name": ["primary_key_unique"], "status": ["PASS"], "failed_count": [0], "failed_sample": [""]})
    calendar = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "is_open": [True]})
    stock_basic = pd.DataFrame({"symbol": ["000001.SZ"], "raw_symbol": ["000001"], "name": ["平安银行"], "exchange": ["SZ"], "is_st": [False]})
    hs300_index = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "symbol": ["000300.SH"], "close": [3500.0]})
    yearly = pd.DataFrame({"year": [2024], "factor_name": ["momentum_20d"], "ic_mean": [0.1]})
    rolling = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "factor_name": ["momentum_20d"], "rolling_60d_rank_ic_mean": [0.1]})
    sensitivity = pd.DataFrame({"factor_name": ["momentum_20d"], "top_quantile": [0.1], "total_return": [0.1]})
    cost_sensitivity = pd.DataFrame({"factor_name": ["momentum_20d"], "cost_scenario": ["default_cost"], "total_return": [0.1]})
    optimization = pd.DataFrame({"rank": [1], "factor_name": ["momentum_20d"], "score": [0.8], "suggested_action": ["keep"]})
    validation = pd.DataFrame({"source_rank": [1], "factor_name": ["momentum_20d"], "validation_status": ["pass"]})
    yearly_validation = pd.DataFrame({"source_rank": [1], "factor_name": ["momentum_20d"], "year": [2024]})

    (tmp_path / "reports").mkdir()
    (tmp_path / "dim").mkdir()
    ingestion_report.to_parquet(tmp_path / "reports" / "ingestion_report.parquet", index=False)
    ingestion_runs.to_parquet(tmp_path / "reports" / "ingestion_runs.parquet", index=False)
    quality.to_parquet(tmp_path / "reports" / "data_quality_report.parquet", index=False)
    calendar.to_parquet(tmp_path / "dim" / "trade_calendar.parquet", index=False)
    stock_basic.to_parquet(tmp_path / "dim" / "stock_basic.parquet", index=False)
    hs300_index.to_parquet(tmp_path / "dim" / "hs300_index.parquet", index=False)
    yearly.to_parquet(tmp_path / "ads" / "factor_yearly_summary.parquet", index=False)
    rolling.to_parquet(tmp_path / "ads" / "factor_rolling_summary.parquet", index=False)
    sensitivity.to_parquet(tmp_path / "ads" / "parameter_sensitivity.parquet", index=False)
    cost_sensitivity.to_parquet(tmp_path / "ads" / "cost_sensitivity.parquet", index=False)
    optimization.to_parquet(tmp_path / "ads" / "strategy_optimization_report.parquet", index=False)
    validation.to_parquet(tmp_path / "ads" / "candidate_validation_report.parquet", index=False)
    yearly_validation.to_parquet(tmp_path / "ads" / "candidate_yearly_validation.parquet", index=False)

    loaded = load_pipeline_outputs(client, tmp_path, factor_name="momentum_20d")

    assert loaded["dim_trade_calendar"] == 1
    assert loaded["dim_stock_basic"] == 1
    assert loaded["dim_hs300_index"] == 1
    assert loaded["ads_factor_yearly_summary"] == 1
    assert loaded["ads_factor_rolling_summary"] == 1
    assert loaded["ads_parameter_sensitivity"] == 1
    assert loaded["ads_cost_sensitivity"] == 1
    assert loaded["ads_strategy_optimization_report"] == 1
    assert loaded["ads_candidate_validation_report"] == 1
    assert loaded["ads_candidate_yearly_validation"] == 1
    assert loaded["ops_ingestion_report"] == 1
    assert loaded["ops_ingestion_runs"] == 1
    assert loaded["ops_data_quality_report"] == 1
    assert [table for table, _ in client.inserts][-13:] == [
        "dim_trade_calendar",
        "dim_stock_basic",
        "dim_hs300_index",
        "ads_factor_yearly_summary",
        "ads_factor_rolling_summary",
        "ads_parameter_sensitivity",
        "ads_cost_sensitivity",
        "ads_strategy_optimization_report",
        "ads_candidate_validation_report",
        "ads_candidate_yearly_validation",
        "ops_ingestion_report",
        "ops_ingestion_runs",
        "ops_data_quality_report",
    ]
