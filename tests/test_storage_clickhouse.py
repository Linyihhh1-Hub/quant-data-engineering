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


def test_load_pipeline_outputs_loads_expected_tables(tmp_path):
    client = FakeClient()
    dwd = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "symbol": ["000001.SZ"]})
    factors = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "symbol": ["000001.SZ"], "momentum_20d": [0.1]})
    eval_report = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "factor_name": ["momentum_20d"], "ic": [0.5]})
    backtest = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "portfolio_value": [1.0]})

    (tmp_path / "dwd").mkdir()
    (tmp_path / "ads").mkdir()
    dwd.to_parquet(tmp_path / "dwd" / "stock_daily.parquet", index=False)
    factors.to_parquet(tmp_path / "ads" / "factor_wide_daily.parquet", index=False)
    eval_report.to_parquet(tmp_path / "ads" / "factor_eval_momentum_20d.parquet", index=False)
    backtest.to_parquet(tmp_path / "ads" / "backtest_daily_momentum_20d.parquet", index=False)

    loaded = load_pipeline_outputs(client, tmp_path, factor_name="momentum_20d")

    assert loaded == {
        "dwd_stock_daily": 1,
        "ads_factor_wide_daily": 1,
        "ads_factor_eval": 1,
        "ads_backtest_daily": 1,
    }
    assert [table for table, _ in client.inserts] == [
        "dwd_stock_daily",
        "ads_factor_wide_daily",
        "ads_factor_eval",
        "ads_backtest_daily",
    ]


def test_load_pipeline_outputs_loads_ops_tables_when_reports_exist(tmp_path):
    client = FakeClient()
    dwd = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "symbol": ["000001.SZ"]})
    factors = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "symbol": ["000001.SZ"], "momentum_20d": [0.1]})
    eval_report = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "factor_name": ["momentum_20d"], "ic": [0.5]})
    backtest = pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")], "portfolio_value": [1.0]})
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

    (tmp_path / "dwd").mkdir()
    (tmp_path / "ads").mkdir()
    (tmp_path / "reports").mkdir()
    dwd.to_parquet(tmp_path / "dwd" / "stock_daily.parquet", index=False)
    factors.to_parquet(tmp_path / "ads" / "factor_wide_daily.parquet", index=False)
    eval_report.to_parquet(tmp_path / "ads" / "factor_eval_momentum_20d.parquet", index=False)
    backtest.to_parquet(tmp_path / "ads" / "backtest_daily_momentum_20d.parquet", index=False)
    ingestion_report.to_parquet(tmp_path / "reports" / "ingestion_report.parquet", index=False)
    ingestion_runs.to_parquet(tmp_path / "reports" / "ingestion_runs.parquet", index=False)
    quality.to_parquet(tmp_path / "reports" / "data_quality_report.parquet", index=False)

    loaded = load_pipeline_outputs(client, tmp_path, factor_name="momentum_20d")

    assert loaded["ops_ingestion_report"] == 1
    assert loaded["ops_ingestion_runs"] == 1
    assert loaded["ops_data_quality_report"] == 1
    assert [table for table, _ in client.inserts][-3:] == [
        "ops_ingestion_report",
        "ops_ingestion_runs",
        "ops_data_quality_report",
    ]
