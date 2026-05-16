# Quant Data Engineering Phase 5 Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a simple factor-based backtest module that selects top-ranked stocks, holds equal-weight positions, applies transaction cost, and reports daily net value and performance metrics.

**Architecture:** Backtest logic lives in `src/quant_data/backtest/simple.py`. The module receives daily bars and factor wide dataframes, computes per-symbol daily returns, forms periodic rebalance portfolios from factor ranks, and returns deterministic result dataframes. It does not read or write files directly.

**Tech Stack:** Python 3.10+, pandas, numpy, pytest.

---

## File Structure

Create these files:

- `src/quant_data/backtest/__init__.py`: package marker.
- `src/quant_data/backtest/simple.py`: simple factor backtest and performance metrics.
- `tests/test_backtest_simple.py`: deterministic unit tests.

Modify:

- `README.md`: add Phase 5 backtest summary.

Code files added in this phase should include necessary Chinese comments for non-obvious backtest logic.

---

## Backtest Contract

Required daily bar columns:

```text
trade_date, symbol, close
```

Required factor columns:

```text
trade_date, symbol, <factor_name>
```

Functions:

```text
select_top_symbols(snapshot, factor_name, top_quantile=0.1) -> list[str]
compute_daily_returns(daily_bars) -> DataFrame
run_simple_backtest(factors, daily_bars, factor_name, top_quantile=0.1, rebalance_interval=20, transaction_cost=0.001) -> tuple[DataFrame, dict[str, float]]
```

`run_simple_backtest` returns:

1. Daily result dataframe:

```text
trade_date, portfolio_value, benchmark_value, daily_return, benchmark_return, drawdown
```

2. Metrics dictionary:

```text
total_return, annualized_return, max_drawdown, sharpe, turnover
```

Rules:

- Rebalance dates are selected from available factor dates every `rebalance_interval` dates.
- On each rebalance date, select stocks in the top `top_quantile` by factor value.
- Portfolio is equal-weighted.
- Positions take effect from the next trading day after rebalance.
- Benchmark is equal-weight return of all available symbols each day.
- Transaction cost is applied on rebalance days after the first position is established.
- Turnover is approximated by absolute weight changes across rebalances.

---

## Tasks

### Task 1: Write Failing Backtest Tests

**Files:**
- Create: `tests/test_backtest_simple.py`

Tests cover:

- `select_top_symbols` selects the top factor names deterministically.
- `compute_daily_returns` computes returns per symbol without leakage.
- `run_simple_backtest` returns expected columns and starts from portfolio value 1.0.
- Metrics include total return, max drawdown, Sharpe, and turnover.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_backtest_simple.py -q
```

Expected: FAIL because `quant_data.backtest.simple` does not exist.

### Task 2: Implement Backtest Module

**Files:**
- Create: `src/quant_data/backtest/__init__.py`
- Create: `src/quant_data/backtest/simple.py`

Implement the three contract functions with Chinese comments for rebalance and net value logic.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_backtest_simple.py -q
```

Expected: PASS.

### Task 3: Run Full Test Suite and Commit

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

Commit:

```powershell
git add src/quant_data/backtest tests/test_backtest_simple.py
git commit -m "Add simple factor backtest"
```

### Task 4: Update README

Append a Phase 5 section summarizing the backtest rules and output metrics.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

Commit:

```powershell
git add README.md
git commit -m "Document simple factor backtest"
```
