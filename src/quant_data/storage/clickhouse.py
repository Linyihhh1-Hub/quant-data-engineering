from pathlib import Path

import pandas as pd


def _clickhouse_type(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "DateTime"
    if pd.api.types.is_integer_dtype(series):
        return "Int64"
    if pd.api.types.is_float_dtype(series):
        return "Float64"
    if pd.api.types.is_bool_dtype(series):
        return "UInt8"
    return "String"


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
    client.command(_create_table_sql(table_name, prepared))
    client.insert_df(table_name, prepared)
    return len(prepared)


def load_pipeline_outputs(client, data_dir: str | Path, factor_name: str) -> dict[str, int]:
    root = Path(data_dir)
    table_files = {
        "dwd_stock_daily": root / "dwd" / "stock_daily.parquet",
        "ads_factor_wide_daily": root / "ads" / "factor_wide_daily.parquet",
        "ads_factor_eval": root / "ads" / f"factor_eval_{factor_name}.parquet",
        "ads_backtest_daily": root / "ads" / f"backtest_daily_{factor_name}.parquet",
    }

    loaded = {}
    for table_name, path in table_files.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing pipeline output: {path}")
        frame = pd.read_parquet(path)
        loaded[table_name] = write_dataframe(client, table_name, frame)
    return loaded
