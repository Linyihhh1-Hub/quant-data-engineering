-- ClickHouse monitoring queries for the quant data engineering pipeline.
-- Run these queries in DBeaver or clickhouse-client after the daily pipeline finishes.

-- 1. Check loaded table row counts.
SELECT 'dim_trade_calendar' AS table_name, count() AS row_count FROM dim_trade_calendar
UNION ALL
SELECT 'dim_stock_basic', count() FROM dim_stock_basic
UNION ALL
SELECT 'dim_hs300_index', count() FROM dim_hs300_index
UNION ALL
SELECT 'dwd_stock_daily', count() FROM dwd_stock_daily
UNION ALL
SELECT 'ads_factor_wide_daily', count() FROM ads_factor_wide_daily
UNION ALL
SELECT 'ads_market_sentiment_daily', count() FROM ads_market_sentiment_daily
UNION ALL
SELECT 'ads_factor_eval', count() FROM ads_factor_eval
UNION ALL
SELECT 'ads_backtest_daily', count() FROM ads_backtest_daily
UNION ALL
SELECT 'ads_factor_yearly_summary', count() FROM ads_factor_yearly_summary
UNION ALL
SELECT 'ads_factor_rolling_summary', count() FROM ads_factor_rolling_summary
UNION ALL
SELECT 'ads_parameter_sensitivity', count() FROM ads_parameter_sensitivity
UNION ALL
SELECT 'ads_cost_sensitivity', count() FROM ads_cost_sensitivity
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

-- 2.1 Check ST stock count in the stock basic dimension.
SELECT
    count() AS stock_count,
    countIf(is_st = 1) AS st_count
FROM dim_stock_basic;

-- 2.2 Check CSI 300 index benchmark coverage.
SELECT
    min(trade_date) AS first_trade_date,
    max(trade_date) AS latest_trade_date,
    count() AS row_count
FROM dim_hs300_index;

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

-- 9.1 Inspect yearly factor and backtest stability.
SELECT
    year,
    factor_name,
    ic_mean,
    rank_ic_mean,
    positive_ic_ratio,
    total_return,
    excess_return,
    max_drawdown,
    sharpe,
    turnover
FROM ads_factor_yearly_summary
ORDER BY factor_name, year;

-- 9.2 Inspect recent rolling stability values.
SELECT
    trade_date,
    factor_name,
    rolling_60d_rank_ic_mean,
    rolling_120d_excess_return,
    rolling_120d_max_drawdown
FROM ads_factor_rolling_summary
ORDER BY trade_date DESC, factor_name
LIMIT 50;

-- 9.3 Inspect parameter sensitivity grid.
SELECT
    factor_name,
    factor_direction,
    top_quantile,
    rebalance_interval,
    total_return,
    gross_total_return,
    excess_return,
    index_excess_return,
    sharpe,
    max_drawdown,
    turnover,
    total_cost,
    cost_drag
FROM ads_parameter_sensitivity
ORDER BY sharpe DESC, excess_return DESC
LIMIT 20;

-- 9.4 Inspect cost sensitivity scenarios.
SELECT
    factor_name,
    factor_direction,
    cost_scenario,
    commission,
    stamp_tax,
    slippage,
    total_return,
    before_cost_total_return,
    cost_drag,
    cost_to_return,
    sharpe,
    turnover
FROM ads_cost_sensitivity
ORDER BY factor_name, cost_scenario;

-- 9.5 Inspect recent market sentiment values.
SELECT
    trade_date,
    market_up_ratio,
    market_strong_ratio,
    market_weak_ratio,
    market_amount_ratio_20d,
    profit_effect,
    market_sentiment_score
FROM ads_market_sentiment_daily
ORDER BY trade_date DESC
LIMIT 20;

-- 10. Inspect the latest backtest net value.
SELECT
    trade_date,
    gross_portfolio_value,
    portfolio_value,
    benchmark_value,
    hs300_benchmark_value,
    daily_return,
    hs300_benchmark_return,
    daily_turnover,
    daily_cost_rate,
    drawdown
FROM ads_backtest_daily
ORDER BY trade_date DESC
LIMIT 20;
