import json
import sys
import types

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
    assert {"total_return", "annualized_return", "max_drawdown", "sharpe", "turnover", "total_cost"} == set(metrics)


def test_cli_ingest_akshare_writes_ods_file(monkeypatch, tmp_path):
    fake = types.ModuleType("akshare")

    def stock_zh_a_hist(symbol: str, period: str, start_date: str, end_date: str, adjust: str):
        return pd.DataFrame(
            [
                {
                    "日期": "2024-01-02",
                    "开盘": 10.0,
                    "最高": 10.5,
                    "最低": 9.8,
                    "收盘": 10.2,
                    "成交量": 1000,
                    "成交额": 10200,
                }
            ]
        )

    fake.stock_zh_a_hist = stock_zh_a_hist
    monkeypatch.setitem(sys.modules, "akshare", fake)

    exit_code = main(
        [
            "ingest-akshare",
            "--symbols",
            "000001,600000",
            "--start-date",
            "20240101",
            "--end-date",
            "20240131",
            "--output",
            str(tmp_path / "ods" / "stock_daily.parquet"),
            "--report",
            str(tmp_path / "reports" / "ingestion_report.parquet"),
            "--run-log",
            str(tmp_path / "reports" / "ingestion_runs.parquet"),
        ]
    )

    result = pd.read_parquet(tmp_path / "ods" / "stock_daily.parquet")
    report = pd.read_parquet(tmp_path / "reports" / "ingestion_report.parquet")
    run_log = pd.read_parquet(tmp_path / "reports" / "ingestion_runs.parquet")
    assert exit_code == 0
    assert result["symbol"].tolist() == ["000001", "600000"]
    assert report["status"].tolist() == ["SUCCESS", "SUCCESS"]
    assert run_log.loc[0, "symbols_count"] == 2


def test_cli_ingest_akshare_reads_symbols_file(monkeypatch, tmp_path):
    fake = types.ModuleType("akshare")

    def stock_zh_a_hist(symbol: str, period: str, start_date: str, end_date: str, adjust: str):
        return pd.DataFrame(
            [
                {
                    "日期": "2024-01-02",
                    "开盘": 10.0,
                    "最高": 10.5,
                    "最低": 9.8,
                    "收盘": 10.2,
                    "成交量": 1000,
                    "成交额": 10200,
                }
            ]
        )

    fake.stock_zh_a_hist = stock_zh_a_hist
    monkeypatch.setitem(sys.modules, "akshare", fake)
    symbols_file = tmp_path / "symbols.csv"
    pd.DataFrame({"symbol": ["000001", "600000", "000001"]}).to_csv(symbols_file, index=False)

    exit_code = main(
        [
            "ingest-akshare",
            "--symbols-file",
            str(symbols_file),
            "--start-date",
            "20240101",
            "--end-date",
            "20240131",
            "--output",
            str(tmp_path / "ods" / "stock_daily.parquet"),
            "--report",
            str(tmp_path / "reports" / "ingestion_report.parquet"),
            "--run-log",
            str(tmp_path / "reports" / "ingestion_runs.parquet"),
        ]
    )

    result = pd.read_parquet(tmp_path / "ods" / "stock_daily.parquet")
    report = pd.read_parquet(tmp_path / "reports" / "ingestion_report.parquet")
    run_log = pd.read_parquet(tmp_path / "reports" / "ingestion_runs.parquet")
    assert exit_code == 0
    assert result["symbol"].tolist() == ["000001", "600000"]
    assert report["symbol"].tolist() == ["000001", "600000"]
    assert run_log.loc[0, "success_count"] == 2


def test_cli_load_clickhouse_uses_pipeline_outputs(monkeypatch, tmp_path):
    calls = {}

    class FakeClient:
        pass

    def fake_get_client(host: str, port: int, username: str, password: str, database: str):
        calls["connection"] = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "database": database,
        }
        return FakeClient()

    def fake_load_pipeline_outputs(client, data_dir, factor_name: str):
        calls["load"] = {
            "client_type": type(client).__name__,
            "data_dir": str(data_dir),
            "factor_name": factor_name,
        }
        return {"dwd_stock_daily": 1}

    monkeypatch.setattr("quant_data.cli.get_clickhouse_client", fake_get_client)
    monkeypatch.setattr("quant_data.cli.load_pipeline_outputs", fake_load_pipeline_outputs)

    exit_code = main(
        [
            "load-clickhouse",
            "--output-dir",
            str(tmp_path),
            "--factor-name",
            "momentum_20d",
            "--host",
            "127.0.0.1",
            "--port",
            "8123",
            "--username",
            "default",
            "--password",
            "secret",
            "--database",
            "quant_data",
        ]
    )

    assert exit_code == 0
    assert calls["connection"] == {
        "host": "127.0.0.1",
        "port": 8123,
        "username": "default",
        "password": "secret",
        "database": "quant_data",
    }
    assert calls["load"] == {
        "client_type": "FakeClient",
        "data_dir": str(tmp_path),
        "factor_name": "momentum_20d",
    }


def test_cli_dimensions_writes_dim_files(monkeypatch, tmp_path):
    calls = {}

    def fake_write_trade_calendar(start_date: str, end_date: str, output_path):
        calls["calendar"] = (start_date, end_date, str(output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"trade_date": [pd.Timestamp("2024-01-02")]}).to_parquet(output_path, index=False)
        return output_path

    def fake_write_stock_basic(output_path):
        calls["stock_basic"] = str(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"symbol": ["000001.SZ"]}).to_parquet(output_path, index=False)
        return output_path

    monkeypatch.setattr("quant_data.cli.write_trade_calendar", fake_write_trade_calendar)
    monkeypatch.setattr("quant_data.cli.write_stock_basic", fake_write_stock_basic)

    exit_code = main(["dimensions", "--start-date", "20240101", "--end-date", "20241231", "--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert calls["calendar"] == ("20240101", "20241231", str(tmp_path / "dim" / "trade_calendar.parquet"))
    assert calls["stock_basic"] == str(tmp_path / "dim" / "stock_basic.parquet")


def test_cli_build_hs300_symbols_writes_config(monkeypatch, tmp_path):
    calls = {}

    def fake_write_hs300_symbol_pool(output_path, filter_st: bool):
        calls["output"] = str(output_path)
        calls["filter_st"] = filter_st
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"symbol": ["000001"], "name": ["平安银行"]}).to_csv(output_path, index=False)
        return output_path

    monkeypatch.setattr("quant_data.cli.write_hs300_symbol_pool", fake_write_hs300_symbol_pool)

    exit_code = main(["build-hs300-symbols", "--output", str(tmp_path / "symbols.csv")])

    assert exit_code == 0
    assert calls == {"output": str(tmp_path / "symbols.csv"), "filter_st": True}
