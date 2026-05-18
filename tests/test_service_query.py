import pandas as pd

from quant_data.service.query import (
    get_factor_eval,
    get_factor_values,
    get_failed_ingestion_symbols,
    get_latest_ingestion_run,
    get_market_sentiment,
    get_quality_failures,
    get_stock_daily,
    get_stock_daily_panel,
)


class FakeQueryClient:
    def __init__(self):
        self.calls = []

    def query_df(self, sql: str, parameters: dict[str, object] | None = None):
        self.calls.append({"sql": sql, "parameters": parameters or {}})
        return pd.DataFrame({"ok": [1]})


def test_get_stock_daily_queries_single_symbol_by_date_range():
    client = FakeQueryClient()

    result = get_stock_daily(client, "000001.SZ", "2024-01-01", "2024-12-31")

    call = client.calls[0]
    assert result["ok"].tolist() == [1]
    assert "FROM dwd_stock_daily" in call["sql"]
    assert "symbol = %(symbol)s" in call["sql"]
    assert call["parameters"] == {
        "symbol": "000001.SZ",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    }


def test_get_stock_daily_panel_queries_multiple_symbols():
    client = FakeQueryClient()

    get_stock_daily_panel(client, ["000001.SZ", "600519.SH"], "2024-01-01", "2024-12-31")

    call = client.calls[0]
    assert "symbol IN %(symbols)s" in call["sql"]
    assert call["parameters"]["symbols"] == ["000001.SZ", "600519.SH"]


def test_get_factor_values_restricts_factor_name_to_known_columns():
    client = FakeQueryClient()

    get_factor_values(
        client,
        "momentum_20d",
        "2024-01-01",
        "2024-12-31",
        symbols=["000001.SZ"],
    )

    call = client.calls[0]
    assert "momentum_20d" in call["sql"]
    assert "symbol IN %(symbols)s" in call["sql"]
    assert call["parameters"]["symbols"] == ["000001.SZ"]


def test_get_factor_values_rejects_unknown_factor_name():
    client = FakeQueryClient()

    try:
        get_factor_values(client, "bad_factor", "2024-01-01", "2024-12-31")
    except ValueError as error:
        assert "Unsupported factor_name" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_monitoring_query_helpers_use_ops_tables():
    client = FakeQueryClient()

    get_factor_eval(client, "momentum_20d")
    get_latest_ingestion_run(client)
    get_failed_ingestion_symbols(client)
    get_quality_failures(client)

    sql_text = "\n".join(call["sql"] for call in client.calls)
    assert "FROM ads_factor_eval" in sql_text
    assert "FROM ops_ingestion_runs" in sql_text
    assert "FROM ops_ingestion_report" in sql_text
    assert "FROM ops_data_quality_report" in sql_text


def test_get_market_sentiment_queries_date_range():
    client = FakeQueryClient()

    get_market_sentiment(client, "2024-01-01", "2024-12-31")

    call = client.calls[0]
    assert "FROM ads_market_sentiment_daily" in call["sql"]
    assert call["parameters"] == {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    }
