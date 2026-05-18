from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from quant_data.storage.clickhouse import get_client

FACTOR_COLUMNS = {
    "momentum_20d",
    "reversal_5d",
    "volatility_20d",
    "volume_ratio_5d",
    "ma_bias_20d",
}


@dataclass(frozen=True)
class ClickHouseConfig:
    host: str = "127.0.0.1"
    port: int = 8123
    username: str = "default"
    password: str = ""
    database: str = "quant_data"


def create_clickhouse_client(config: ClickHouseConfig):
    return get_client(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        database=config.database,
    )


def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
    result = [symbol.strip() for symbol in symbols if symbol and symbol.strip()]
    if not result:
        raise ValueError("symbols must not be empty")
    return result


def _validate_factor_name(factor_name: str) -> str:
    if factor_name not in FACTOR_COLUMNS:
        supported = ", ".join(sorted(FACTOR_COLUMNS))
        raise ValueError(f"Unsupported factor_name: {factor_name}. Supported factors: {supported}")
    return factor_name


def get_stock_daily(
    client,
    symbol: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    sql = """
    SELECT
        trade_date,
        symbol,
        open,
        high,
        low,
        close,
        volume,
        amount,
        return_1d
    FROM dwd_stock_daily
    WHERE symbol = %(symbol)s
      AND trade_date BETWEEN %(start_date)s AND %(end_date)s
    ORDER BY trade_date
    """
    return client.query_df(
        sql,
        parameters={
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
        },
    )


def get_stock_daily_panel(
    client,
    symbols: Iterable[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    symbol_list = _normalize_symbols(symbols)
    sql = """
    SELECT
        trade_date,
        symbol,
        open,
        high,
        low,
        close,
        volume,
        amount,
        return_1d
    FROM dwd_stock_daily
    WHERE symbol IN %(symbols)s
      AND trade_date BETWEEN %(start_date)s AND %(end_date)s
    ORDER BY trade_date, symbol
    """
    return client.query_df(
        sql,
        parameters={
            "symbols": symbol_list,
            "start_date": start_date,
            "end_date": end_date,
        },
    )


def get_factor_values(
    client,
    factor_name: str,
    start_date: str,
    end_date: str,
    symbols: Iterable[str] | None = None,
) -> pd.DataFrame:
    factor_column = _validate_factor_name(factor_name)
    parameters: dict[str, object] = {
        "start_date": start_date,
        "end_date": end_date,
    }
    symbol_filter = ""
    if symbols is not None:
        parameters["symbols"] = _normalize_symbols(symbols)
        symbol_filter = "AND symbol IN %(symbols)s"

    # factor_column 来自白名单，避免把任意字符串拼进 SELECT 字段名。
    sql = f"""
    SELECT
        trade_date,
        symbol,
        {factor_column} AS factor_value
    FROM ads_factor_wide_daily
    WHERE trade_date BETWEEN %(start_date)s AND %(end_date)s
      {symbol_filter}
    ORDER BY trade_date, symbol
    """
    return client.query_df(sql, parameters=parameters)


def get_factor_eval(client, factor_name: str) -> pd.DataFrame:
    sql = """
    SELECT
        trade_date,
        factor_name,
        ic,
        rank_ic,
        top_group_return,
        bottom_group_return,
        long_short_return
    FROM ads_factor_eval
    WHERE factor_name = %(factor_name)s
    ORDER BY trade_date
    """
    return client.query_df(sql, parameters={"factor_name": factor_name})


def get_latest_ingestion_run(client) -> pd.DataFrame:
    sql = """
    SELECT *
    FROM ops_ingestion_runs
    ORDER BY ended_at DESC
    LIMIT 1
    """
    return client.query_df(sql)


def get_failed_ingestion_symbols(client) -> pd.DataFrame:
    sql = """
    SELECT
        symbol,
        status,
        row_count,
        message
    FROM ops_ingestion_report
    WHERE status != 'SUCCESS' AND status != 'SKIPPED'
    ORDER BY symbol
    """
    return client.query_df(sql)


def get_quality_failures(client) -> pd.DataFrame:
    sql = """
    SELECT
        rule_name,
        status,
        failed_count,
        failed_sample
    FROM ops_data_quality_report
    WHERE status != 'PASS'
    ORDER BY failed_count DESC
    """
    return client.query_df(sql)
