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
    assert (tmp_path / "ads" / "market_sentiment_daily.parquet").exists()
    assert (tmp_path / "ads" / "factor_eval_momentum_20d.parquet").exists()
    assert (tmp_path / "ads" / "backtest_daily_momentum_20d.parquet").exists()
    assert (tmp_path / "ads" / "factor_yearly_summary.parquet").exists()
    assert (tmp_path / "ads" / "factor_rolling_summary.parquet").exists()
    assert (tmp_path / "ads" / "parameter_sensitivity.parquet").exists()

    metrics_path = tmp_path / "ads" / "backtest_metrics_momentum_20d.json"
    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert {
        "total_return",
        "gross_total_return",
        "cost_drag",
        "cost_return_ratio",
        "annualized_return",
        "equal_weight_total_return",
        "hs300_total_return",
        "hs300_excess_return",
        "max_drawdown",
        "sharpe",
        "turnover",
        "total_cost",
        "average_exposure",
        "factor_direction",
        "entry_quantile",
        "exit_quantile",
        "average_turnover_per_rebalance",
    }.issubset(metrics)


def test_cli_run_all_merges_stock_basic_into_dwd(tmp_path):
    raw_path = tmp_path / "ods" / "stock_daily.parquet"
    raw_path.parent.mkdir(parents=True)
    make_pipeline_raw_frame().to_parquet(raw_path, index=False)
    dim_dir = tmp_path / "dim"
    dim_dir.mkdir()
    pd.DataFrame(
        [
            {"symbol": "000001.SZ", "name": "平安银行", "exchange": "SZ", "is_st": False},
            {"symbol": "000002.SZ", "name": "ST测试", "exchange": "SZ", "is_st": True},
            {"symbol": "600000.SH", "name": "浦发银行", "exchange": "SH", "is_st": False},
            {"symbol": "600001.SH", "name": "邯郸钢铁", "exchange": "SH", "is_st": False},
        ]
    ).to_parquet(dim_dir / "stock_basic.parquet", index=False)

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
            "--exclude-st",
        ]
    )

    dwd = pd.read_parquet(tmp_path / "dwd" / "stock_daily.parquet")
    assert exit_code == 0
    assert {"is_st", "name", "exchange"}.issubset(dwd.columns)
    assert dwd.loc[dwd["symbol"] == "000002.SZ", "is_st"].all()


def test_cli_run_all_supports_sentiment_timing_backtest(tmp_path):
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
            "--sentiment-threshold",
            "0",
            "--weak-sentiment-exposure",
            "0.3",
        ]
    )

    daily_result = pd.read_parquet(tmp_path / "ads" / "backtest_daily_momentum_20d.parquet")
    metrics = json.loads((tmp_path / "ads" / "backtest_metrics_momentum_20d.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert "target_exposure" in daily_result.columns
    assert "average_exposure" in metrics
    assert daily_result["target_exposure"].between(0.3, 1.0).all()


def test_cli_factor_suite_writes_outputs_for_multiple_factors(tmp_path):
    raw_path = tmp_path / "ods" / "stock_daily.parquet"
    raw_path.parent.mkdir(parents=True)
    make_pipeline_raw_frame().to_parquet(raw_path, index=False)

    main(
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
    exit_code = main(
        [
            "factor-suite",
            "--output-dir",
            str(tmp_path),
            "--factor-names",
            "momentum_20d,reversal_5d",
            "--horizon",
            "1",
            "--groups",
            "2",
            "--top-quantile",
            "0.5",
            "--rebalance-interval",
            "5",
            "--sentiment-threshold",
            "0",
            "--weak-sentiment-exposure",
            "0.3",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "ads" / "factor_eval_momentum_20d.parquet").exists()
    assert (tmp_path / "ads" / "factor_eval_reversal_5d.parquet").exists()
    assert (tmp_path / "ads" / "backtest_daily_momentum_20d.parquet").exists()
    assert (tmp_path / "ads" / "backtest_daily_reversal_5d.parquet").exists()
    yearly = pd.read_parquet(tmp_path / "ads" / "factor_yearly_summary.parquet")
    rolling = pd.read_parquet(tmp_path / "ads" / "factor_rolling_summary.parquet")
    assert set(yearly["factor_name"].unique()) == {"momentum_20d", "reversal_5d"}
    assert set(rolling["factor_name"].unique()) == {"momentum_20d", "reversal_5d"}
    metrics = json.loads((tmp_path / "ads" / "backtest_metrics_reversal_5d.json").read_text(encoding="utf-8"))
    assert "average_exposure" in metrics


def test_cli_stability_writes_yearly_and_rolling_reports(tmp_path):
    raw_path = tmp_path / "ods" / "stock_daily.parquet"
    raw_path.parent.mkdir(parents=True)
    make_pipeline_raw_frame().to_parquet(raw_path, index=False)

    main(
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
    exit_code = main(
        [
            "stability",
            "--output-dir",
            str(tmp_path),
            "--factor-names",
            "momentum_20d",
            "--rank-ic-window",
            "5",
            "--return-window",
            "10",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "ads" / "factor_yearly_summary.parquet").exists()
    assert (tmp_path / "ads" / "factor_rolling_summary.parquet").exists()


def test_cli_sensitivity_writes_parameter_grid(tmp_path):
    raw_path = tmp_path / "ods" / "stock_daily.parquet"
    raw_path.parent.mkdir(parents=True)
    make_pipeline_raw_frame().to_parquet(raw_path, index=False)

    main(
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
    exit_code = main(
        [
            "sensitivity",
            "--output-dir",
            str(tmp_path),
            "--factor-name",
            "momentum_20d",
            "--top-quantiles",
            "0.5,1.0",
            "--rebalance-intervals",
            "5,10",
            "--factor-directions",
            "top",
        ]
    )

    result = pd.read_parquet(tmp_path / "ads" / "parameter_sensitivity.parquet")
    assert exit_code == 0
    assert len(result) == 4


def test_cli_optimize_strategy_writes_recommendation_report(tmp_path):
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

    exit_code = main(["optimize-strategy", "--output-dir", str(tmp_path)])

    result = pd.read_parquet(tmp_path / "ads" / "strategy_optimization_report.parquet")
    assert exit_code == 0
    assert result.loc[0, "factor_name"] == "factor"
    assert "suggested_action" in result.columns


def test_cli_validate_candidates_writes_reports(tmp_path):
    ads_dir = tmp_path / "ads"
    dwd_dir = tmp_path / "dwd"
    ads_dir.mkdir(parents=True)
    dwd_dir.mkdir(parents=True)
    rows = []
    factor_rows = []
    for day_index in range(12):
        trade_date = pd.Timestamp("2024-01-01") + pd.Timedelta(days=day_index)
        for symbol_index, symbol in enumerate(["AAA", "BBB", "CCC", "DDD"]):
            rows.append({"trade_date": trade_date, "symbol": symbol, "close": 10 + day_index + symbol_index})
            factor_rows.append({"trade_date": trade_date, "symbol": symbol, "test_factor": float(symbol_index)})
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

    exit_code = main(
        [
            "validate-candidates",
            "--output-dir",
            str(tmp_path),
            "--top-n",
            "1",
            "--validation-start",
            "20240107",
            "--transaction-cost",
            "0",
        ]
    )

    assert exit_code == 0
    assert (ads_dir / "candidate_validation_report.parquet").exists()
    assert (ads_dir / "candidate_yearly_validation.parquet").exists()


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


def test_cli_ingest_hs300_index_writes_dim_file(monkeypatch, tmp_path):
    calls = {}

    def fake_write_hs300_index(start_date: str, end_date: str, output_path):
        calls["args"] = (start_date, end_date, str(output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"trade_date": [pd.Timestamp("2020-01-02")], "symbol": ["000300.SH"], "close": [100.0]}).to_parquet(
            output_path, index=False
        )
        return output_path

    monkeypatch.setattr("quant_data.cli.write_hs300_index", fake_write_hs300_index)

    exit_code = main(["ingest-hs300-index", "--start-date", "20200101", "--end-date", "20241231", "--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert calls["args"] == ("20200101", "20241231", str(tmp_path / "dim" / "hs300_index.parquet"))
