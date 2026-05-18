from pathlib import Path

import pandas as pd


def _clickhouse_type(series: pd.Series) -> str:
    nullable = bool(series.isna().any())
    if pd.api.types.is_datetime64_any_dtype(series):
        base_type = "DateTime"
    elif pd.api.types.is_integer_dtype(series):
        base_type = "Int64"
    elif pd.api.types.is_float_dtype(series):
        base_type = "Float64"
    elif pd.api.types.is_bool_dtype(series):
        base_type = "UInt8"
    else:
        base_type = "String"
    if nullable:
        return f"Nullable({base_type})"
    return base_type


def _create_table_sql(table_name: str, frame: pd.DataFrame) -> str:
    columns = []
    for column in frame.columns:
        columns.append(f"`{column}` {_clickhouse_type(frame[column])}")
    column_sql = ",\n  ".join(columns)
    return f"CREATE TABLE {table_name} (\n  {column_sql}\n) ENGINE = MergeTree ORDER BY tuple()"


def _prepare_for_insert(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        if pd.api.types.is_datetime64_any_dtype(result[column]):
            result[column] = pd.to_datetime(result[column]).dt.tz_localize(None)
            result[column] = result[column].astype("object").where(result[column].notna(), None)
    return result


def get_client(host: str, port: int, username: str, password: str, database: str):
    from clickhouse_connect import get_client as connect

    return connect(host=host, port=port, username=username, password=password, database=database)


def write_dataframe(client, table_name: str, frame: pd.DataFrame) -> int:
    if frame.empty:
        client.command(f"DROP TABLE IF EXISTS {table_name}")
        client.command(f"CREATE TABLE {table_name} (`empty_marker` String) ENGINE = MergeTree ORDER BY tuple()")
        return 0

    prepared = _prepare_for_insert(frame)
    # 这里使用覆盖式写入，保证重复运行 CLI 时 ClickHouse 表与当前 Parquet 结果一致。
    client.command(f"DROP TABLE IF EXISTS {table_name}")
    client.command(_create_table_sql(table_name, frame))
    client.insert_df(table_name, prepared)
    return len(prepared)


def load_pipeline_outputs(client, data_dir: str | Path, factor_name: str) -> dict[str, int]:
    root = Path(data_dir)
    required_table_files = {
        "dwd_stock_daily": root / "dwd" / "stock_daily.parquet",
        "ads_factor_wide_daily": root / "ads" / "factor_wide_daily.parquet",
        "ads_factor_eval": root / "ads" / f"factor_eval_{factor_name}.parquet",
        "ads_backtest_daily": root / "ads" / f"backtest_daily_{factor_name}.parquet",
    }
    optional_table_files = {
        "dim_trade_calendar": root / "dim" / "trade_calendar.parquet",
        "dim_stock_basic": root / "dim" / "stock_basic.parquet",
        "ops_ingestion_report": root / "reports" / "ingestion_report.parquet",
        "ops_ingestion_runs": root / "reports" / "ingestion_runs.parquet",
        "ops_data_quality_report": root / "reports" / "data_quality_report.parquet",
    }

    loaded = {}
    for table_name, path in required_table_files.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing pipeline output: {path}")
        frame = pd.read_parquet(path)
        loaded[table_name] = write_dataframe(client, table_name, frame)
    for table_name, path in optional_table_files.items():
        if path.exists():
            # OPS 表来自采集和质量检查报告，存在时同步入库，便于用 SQL 做任务审计和质量巡检。
            frame = pd.read_parquet(path)
            loaded[table_name] = write_dataframe(client, table_name, frame)
    return loaded
