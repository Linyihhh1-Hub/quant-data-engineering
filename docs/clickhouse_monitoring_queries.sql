-- ClickHouse monitoring queries for the quant data engineering pipeline.
-- Run these queries in DBeaver or clickhouse-client after the daily pipeline finishes.

-- 1. Check loaded table row counts.
SELECT 'dwd_stock_daily' AS table_name, count() AS row_count FROM dwd_stock_daily
UNION ALL
SELECT 'ads_factor_wide_daily', count() FROM ads_factor_wide_daily
UNION ALL
SELECT 'ads_factor_eval', count() FROM ads_factor_eval
UNION ALL
SELECT 'ads_backtest_daily', count() FROM ads_backtest_daily
UNION ALL
SELECT 'ops_ingestion_report', count() FROM ops_ingestion_report
UNION ALL
SELECT 'ops_ingestion_runs', count() FROM ops_ingestion_runs
UNION ALL
SELECT 'ops_data_quality_report', count() FROM ops_data_quality_report;

-- 2. Check latest available trade date and stock coverage.
SELECT
    max(trade_date) AS latest_trade_date,
    uniqExact(symbol) AS symbol_count,
    count() AS row_count
FROM dwd_stock_daily;

-- 3. Check row count by stock.
SELECT
    symbol,
    min(trade_date) AS first_trade_date,
    max(trade_date) AS latest_trade_date,
    count() AS row_count
FROM dwd_stock_daily
GROUP BY symbol
ORDER BY symbol;

-- 4. Check ingestion status by symbol.
SELECT
    status,
    count() AS symbol_count,
    sum(row_count) AS fetched_rows
FROM ops_ingestion_report
GROUP BY status
ORDER BY status;

-- 5. List failed ingestion symbols.
SELECT
    symbol,
    status,
    message
FROM ops_ingestion_report
WHERE status != 'SUCCESS' AND status != 'SKIPPED'
ORDER BY symbol;

-- 6. Inspect the latest ingestion run.
SELECT *
FROM ops_ingestion_runs
ORDER BY ended_at DESC
LIMIT 1;

-- 7. Check data quality failures.
SELECT
    rule_name,
    status,
    failed_count,
    failed_sample
FROM ops_data_quality_report
WHERE status != 'PASS'
ORDER BY failed_count DESC;

-- 8. Check factor coverage by date.
SELECT
    trade_date,
    count() AS total_rows,
    countIf(isNotNull(momentum_20d)) AS momentum_20d_rows,
    countIf(isNotNull(momentum_20d)) / count() AS momentum_20d_coverage
FROM ads_factor_wide_daily
GROUP BY trade_date
ORDER BY trade_date DESC
LIMIT 20;

-- 9. Inspect recent factor evaluation results.
SELECT
    trade_date,
    factor_name,
    ic,
    rank_ic,
    long_short_return
FROM ads_factor_eval
ORDER BY trade_date DESC
LIMIT 20;

-- 10. Inspect the latest backtest net value.
SELECT
    trade_date,
    portfolio_value,
    benchmark_value,
    daily_return,
    drawdown
FROM ads_backtest_daily
ORDER BY trade_date DESC
LIMIT 20;
