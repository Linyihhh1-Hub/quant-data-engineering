# Quant Data Engineering MVP Design

Date: 2026-05-16
Project: A-share Quant Factor Data Engineering and Backtest Dataset

## Goal

Build a local, runnable quant data engineering project for resume and interview use. The project demonstrates a complete data pipeline:

```text
Ingestion -> ODS -> DWD -> ADS -> Data Quality -> Factor Evaluation -> Simple Backtest
```

The first version prioritizes data engineering quality over strategy profitability. It should prove the ability to build reusable data pipelines, layered datasets, quality checks, factor tables, and basic research datasets.

## Scope

Included in MVP:

- A-share daily market data ingestion from AkShare.
- ODS, DWD, and ADS data layers stored as Parquet files.
- Cleaning and standardization for dates, symbols, numeric fields, and daily returns.
- Data quality checks for uniqueness, nulls, price validity, volume validity, date completeness, and abnormal return flags.
- Five baseline factors: momentum_20d, reversal_5d, volatility_20d, volume_ratio_5d, ma_bias_20d.
- Factor evaluation with IC, RankIC, and grouped returns.
- Simple monthly rebalancing backtest based on factor ranking.
- CLI commands for each pipeline stage.
- Unit tests using small fixture datasets, not live network data.

Excluded from MVP:

- Tick-level or high-frequency data.
- Live trading or broker integration.
- Web UI or API service.
- Complex alpha mining or machine learning models.
- Airflow, DolphinScheduler, ClickHouse, or Docker integration.

## Technical Stack

- Python 3.10+
- pandas
- numpy
- DuckDB
- PyArrow / Parquet
- AkShare
- pytest
- PyYAML

Optional future extensions:

- polars for faster local processing
- ClickHouse for analytical storage
- Airflow or DolphinScheduler for orchestration
- Streamlit or FastAPI for presentation/query service

## Directory Structure

```text
量化项目/
├── README.md
├── pyproject.toml
├── configs/
│   ├── data.yaml
│   └── factors.yaml
├── data/
│   ├── ods/
│   ├── dwd/
│   ├── ads/
│   └── reports/
├── src/
│   └── quant_data/
│       ├── __init__.py
│       ├── config.py
│       ├── cli.py
│       ├── ingestion/
│       ├── cleaning/
│       ├── quality/
│       ├── factors/
│       ├── evaluation/
│       ├── backtest/
│       └── storage/
└── tests/
```

## Data Layers

### ODS

`ods_stock_daily` keeps raw daily market data fetched from AkShare. Only field names and basic file layout are standardized. Business cleaning is not applied here.

Expected fields:

```text
trade_date, symbol, open, high, low, close, volume, amount
```

### DWD

`dwd_stock_daily` stores cleaned daily bars. It performs type conversion, date normalization, symbol normalization, sorting, duplicate handling, and daily return calculation.

Expected fields:

```text
trade_date, symbol, open, high, low, close, volume, amount, return_1d
```

### ADS

`ads_factor_wide_daily` stores one row per trading date and stock symbol, with all baseline factor values in columns.

Expected fields:

```text
trade_date, symbol, momentum_20d, reversal_5d, volatility_20d, volume_ratio_5d, ma_bias_20d
```

`ads_factor_eval` stores factor effectiveness metrics.

Expected fields:

```text
trade_date, factor_name, ic, rank_ic, top_group_return, bottom_group_return, long_short_return
```

`ads_backtest_daily` stores portfolio performance.

Expected fields:

```text
date, portfolio_value, benchmark_value, daily_return, drawdown
```

## Data Quality Rules

The MVP implements these rules:

1. Primary key uniqueness: `trade_date + symbol` must be unique.
2. Required field non-null checks for `open`, `high`, `low`, `close`, and `volume`.
3. Price validity: `high >= low`, `close > 0`, and prices must be non-negative.
4. Volume validity: `volume >= 0`.
5. Date completeness: each trade date must have at least a configurable minimum number of stock rows.
6. Abnormal return flag: rows with absolute one-day return above a configurable threshold are reported.

Quality results are written to:

```text
data/reports/data_quality_report.parquet
```

## Factor Computation

The MVP computes five baseline factors:

```text
momentum_20d   = close / close.shift(20) - 1
reversal_5d    = -1 * (close / close.shift(5) - 1)
volatility_20d = rolling_std(return_1d, 20)
volume_ratio_5d = volume / rolling_mean(volume, 5)
ma_bias_20d    = close / rolling_mean(close, 20) - 1
```

All rolling calculations are grouped by symbol and sorted by trade date.

## Factor Evaluation

For each factor and trade date range, compute:

- IC: Pearson correlation between factor value and future N-day return.
- RankIC: Spearman correlation between factor rank and future N-day return rank.
- Grouped returns: divide stocks into five quantile groups and compare top versus bottom group future returns.

Default forward return horizon: 5 trading days.

## Backtest

The MVP implements a simple cross-sectional monthly rebalancing backtest:

- Select one factor as ranking signal.
- On each rebalance date, buy the top 10% stocks by factor value.
- Use equal weights.
- Apply fixed transaction cost of 0.1% per rebalance.
- Compare against a configurable benchmark later; MVP can use equal-weight universe return as fallback.
- Output annualized return, maximum drawdown, Sharpe ratio, turnover, and daily net value series.

The backtest is used to validate the factor dataset, not to claim production strategy performance.

## CLI Design

The package exposes command-line stages:

```powershell
python -m quant_data.cli ingest --start-date 2023-01-01 --end-date 2025-12-31
python -m quant_data.cli clean
python -m quant_data.cli quality
python -m quant_data.cli factors
python -m quant_data.cli evaluate
python -m quant_data.cli backtest
python -m quant_data.cli run-all
```

Each command reads configuration from `configs/` and writes outputs to the corresponding `data/` subdirectory.

## Testing Strategy

Unit tests use small fixed fixture datasets. Tests do not call AkShare or any live network service.

Priority tests:

- Config loading returns expected defaults and paths.
- Cleaning normalizes dates, sorts rows, handles duplicates, and computes `return_1d`.
- Quality rules detect duplicate keys, null required fields, invalid prices, invalid volume, and abnormal returns.
- Factor calculations match expected values on deterministic fixture data.
- IC and RankIC calculations return expected values on controlled inputs.
- Backtest metrics compute drawdown, Sharpe, and portfolio value correctly.

Network ingestion can be checked manually or through a separate integration test later.

## Implementation Order

1. Initialize project structure and dependency configuration.
2. Add config loading.
3. Add Parquet storage helpers.
4. Add DWD cleaning logic.
5. Add data quality rules.
6. Add baseline factor calculation.
7. Add factor evaluation.
8. Add simple backtest.
9. Add AkShare ingestion CLI.
10. Add README, usage examples, and resume description.

## Resume Positioning

Resume description should emphasize data engineering:

```text
Built an A-share quant factor data engineering pipeline with ODS-DWD-ADS layered datasets, daily market data cleaning, data quality checks, baseline factor computation, IC/RankIC evaluation, and simple monthly rebalancing backtest dataset generation using Python, DuckDB, and Parquet.
```
