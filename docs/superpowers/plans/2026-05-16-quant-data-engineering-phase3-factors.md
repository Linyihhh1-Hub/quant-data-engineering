# Quant Data Engineering Phase 3 Factors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add baseline factor calculation for cleaned daily market data and produce an ADS-style factor wide table.

**Architecture:** Factor logic lives in `src/quant_data/factors/baseline.py`. The module accepts a cleaned DWD daily-bar DataFrame and returns a DataFrame with `trade_date`, `symbol`, and factor columns. It does not read or write files directly.

**Tech Stack:** Python 3.10+, pandas, pytest.

---

## File Structure

Create these files:

- `src/quant_data/factors/__init__.py`: package marker.
- `src/quant_data/factors/baseline.py`: baseline factor formulas.
- `tests/test_factors_baseline.py`: deterministic unit tests for factor formulas.

Modify:

- `README.md`: add Phase 3 factor module summary.

---

## Factor Contract

`compute_baseline_factors(frame)` returns a DataFrame with these columns:

```text
trade_date, symbol, momentum_20d, reversal_5d, volatility_20d, volume_ratio_5d, ma_bias_20d
```

Required input columns:

```text
trade_date, symbol, close, volume, return_1d
```

All calculations are grouped by `symbol` and sorted by `symbol, trade_date`.

Factor formulas:

```text
momentum_20d = close / close.shift(20) - 1
reversal_5d = -1 * (close / close.shift(5) - 1)
volatility_20d = rolling_std(return_1d, 20)
volume_ratio_5d = volume / rolling_mean(volume, 5)
ma_bias_20d = close / rolling_mean(close, 20) - 1
```

Rolling windows use `min_periods` equal to the full window, so early rows return null factor values.

---

## Tasks

### Task 1: Write Failing Factor Tests

**Files:**
- Create: `tests/test_factors_baseline.py`

Write tests that construct deterministic daily bars for one or two symbols and assert:

- Output contains expected factor columns.
- Rows are sorted by `symbol, trade_date`.
- `momentum_20d` equals `close / close.shift(20) - 1`.
- `reversal_5d` equals negative 5-day return.
- `volume_ratio_5d` equals current volume divided by 5-day average volume.
- `ma_bias_20d` equals close divided by 20-day moving average minus 1.
- Factor calculations do not leak across symbols.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_factors_baseline.py -q
```

Expected: FAIL because `quant_data.factors.baseline` does not exist.

### Task 2: Implement Factor Module

**Files:**
- Create: `src/quant_data/factors/__init__.py`
- Create: `src/quant_data/factors/baseline.py`

Implement:

- `FACTOR_COLUMNS`
- `compute_baseline_factors(frame: pd.DataFrame) -> pd.DataFrame`

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_factors_baseline.py -q
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
git add src/quant_data/factors tests/test_factors_baseline.py
git commit -m "Add baseline factor calculations"
```

### Task 4: Update README

Append a Phase 3 section summarizing factor columns and formulas.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

Commit:

```powershell
git add README.md
git commit -m "Document baseline factor calculations"
```
