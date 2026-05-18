# Quant Data Engineering

Local A-share quant data engineering project for building layered market datasets, quality checks, factor tables, and simple backtest datasets.

## Phase 1

Implemented foundation:

- Python package skeleton
- YAML config loading
- Parquet storage helpers
- DWD daily bar cleaning
- Unit tests with fixture data

## Development

Install in editable mode:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Phase 2: Data Quality

Implemented daily market data quality checks:

- `primary_key_unique`: `trade_date + symbol` has no duplicates
- `required_fields_not_null`: required OHLCV fields are not null
- `price_valid`: prices are non-negative, `close > 0`, and `high >= low`
- `volume_valid`: `volume >= 0`
- `date_completeness`: each trading date has at least the configured number of rows
- `abnormal_return`: absolute daily return above the configured threshold is reported

Quality report schema:

```text
rule_name, status, failed_count, failed_sample
```

## Phase 3: Baseline Factors

Implemented ADS-style factor wide table generation from cleaned daily bars.

Output columns:

```text
trade_date, symbol, momentum_20d, reversal_5d, volatility_20d, volume_ratio_5d, ma_bias_20d
```

Factor formulas:

```text
momentum_20d = close / close.shift(20) - 1
reversal_5d = -1 * (close / close.shift(5) - 1)
volatility_20d = rolling_std(return_1d, 20)
volume_ratio_5d = volume / rolling_mean(volume, 5)
ma_bias_20d = close / rolling_mean(close, 20) - 1
```

All rolling calculations are grouped by `symbol` and sorted by `symbol, trade_date`.

## Phase 4: Factor Evaluation

Implemented factor effectiveness evaluation:

- Forward return by symbol: `close.shift(-horizon) / close - 1`
- IC: cross-sectional Pearson correlation between factor value and forward return
- RankIC: Pearson correlation between factor rank and forward return rank
- Grouped returns: compare top group, bottom group, and long-short return

Evaluation report schema:

```text
trade_date, factor_name, ic, rank_ic, top_group_return, bottom_group_return, long_short_return
```

## Phase 5: Simple Backtest

Implemented a simple factor-based backtest:

- Select stocks in the top factor quantile on rebalance dates
- Hold selected stocks with equal weights
- Apply configurable transaction cost on rebalances after initial position setup
- Use equal-weight universe return as benchmark
- Output daily portfolio net value, benchmark net value, daily return, benchmark return, and drawdown

Backtest metrics:

```text
total_return, annualized_return, max_drawdown, sharpe, turnover
```

## CLI Pipeline

Fetch real A-share daily data with AkShare:

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli ingest-akshare `
  --symbols 000001,600000,600519 `
  --start-date 20240101 `
  --end-date 20241231 `
  --adjust qfq `
  --output data/ods/stock_daily.parquet
```

You can also manage the universe with a CSV stock pool:

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli ingest-akshare `
  --symbols-file configs/symbols.csv `
  --start-date 20240101 `
  --end-date 20241231 `
  --adjust qfq `
  --output data/ods/stock_daily.parquet `
  --report data/reports/ingestion_report.parquet `
  --retries 3 `
  --retry-wait-seconds 2 `
  --incremental `
  --run-log data/reports/ingestion_runs.parquet
```

The stock pool file must contain a `symbol` column. The ingestion report records per-symbol status:

```text
symbol, status, row_count, message
```

Use `--incremental` to fetch only dates newer than each symbol's latest local ODS record. Use `--run-log` to append one summary row for each ingestion run.

Run all local pipeline stages from a raw ODS Parquet file:

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli run-all `
  --input data/ods/stock_daily.parquet `
  --output-dir data `
  --factor-name momentum_20d
```

Stage outputs:

```text
data/dwd/stock_daily.parquet
data/reports/data_quality_report.parquet
data/ads/factor_wide_daily.parquet
data/ads/factor_eval_<factor_name>.parquet
data/ads/backtest_daily_<factor_name>.parquet
data/ads/backtest_metrics_<factor_name>.json
```

Chinese documentation: [README.zh-CN.md](README.zh-CN.md)

Data dictionary in Chinese: [docs/data_dictionary.zh-CN.md](docs/data_dictionary.zh-CN.md)

## ClickHouse Load

Load generated Parquet outputs into local ClickHouse:

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli load-clickhouse `
  --output-dir data `
  --factor-name momentum_20d `
  --host 127.0.0.1 `
  --port 8123 `
  --username default `
  --password <your-clickhouse-password> `
  --database quant_data
```

Created tables:

```text
dwd_stock_daily
ads_factor_wide_daily
ads_factor_eval
ads_backtest_daily
```
