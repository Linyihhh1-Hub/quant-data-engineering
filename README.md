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
