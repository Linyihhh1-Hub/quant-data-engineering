# Quant Data Engineering Phase 4 Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add factor effectiveness evaluation with forward returns, IC, RankIC, and grouped returns.

**Architecture:** Evaluation logic lives in `src/quant_data/evaluation/factor.py`. The module receives cleaned daily bars and factor wide dataframes, computes forward returns by symbol, joins factor values, and returns normalized evaluation tables. It does not read or write files directly.

**Tech Stack:** Python 3.10+, pandas, pytest.

---

## File Structure

Create these files:

- `src/quant_data/evaluation/__init__.py`: package marker.
- `src/quant_data/evaluation/factor.py`: forward return, IC/RankIC, grouped return calculations.
- `tests/test_evaluation_factor.py`: deterministic unit tests.

Modify:

- `README.md`: add Phase 4 evaluation summary.

---

## Evaluation Contract

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
add_forward_return(daily_bars, horizon=5) -> DataFrame
compute_ic_report(factors, daily_bars, factor_name, horizon=5) -> DataFrame
compute_group_return_report(factors, daily_bars, factor_name, horizon=5, groups=5) -> DataFrame
evaluate_factor(factors, daily_bars, factor_name, horizon=5, groups=5) -> DataFrame
```

`add_forward_return` computes:

```text
forward_return = close.shift(-horizon) / close - 1
```

by symbol.

`compute_ic_report` returns columns:

```text
trade_date, factor_name, ic, rank_ic
```

IC is Pearson correlation between factor values and forward returns for each trade date.
RankIC is Spearman correlation between factor ranks and forward return ranks for each trade date.

`compute_group_return_report` returns columns:

```text
trade_date, factor_name, top_group_return, bottom_group_return, long_short_return
```

Rows with null factor or forward return are excluded. If a trade date has fewer unique factor values than requested groups, that date is skipped.

`evaluate_factor` merges IC and group reports on `trade_date` and `factor_name`.

---

## Tasks

### Task 1: Write Failing Evaluation Tests

**Files:**
- Create: `tests/test_evaluation_factor.py`

Tests cover:

- Forward return is computed per symbol without leakage.
- IC and RankIC are computed per trade date.
- Grouped returns produce top, bottom, and long-short returns.
- `evaluate_factor` returns a merged report.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_evaluation_factor.py -q
```

Expected: FAIL because `quant_data.evaluation.factor` does not exist.

### Task 2: Implement Evaluation Module

**Files:**
- Create: `src/quant_data/evaluation/__init__.py`
- Create: `src/quant_data/evaluation/factor.py`

Implement the four contract functions.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_evaluation_factor.py -q
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
git add src/quant_data/evaluation tests/test_evaluation_factor.py
git commit -m "Add factor evaluation metrics"
```

### Task 4: Update README

Append a Phase 4 section summarizing IC, RankIC, and grouped return outputs.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

Commit:

```powershell
git add README.md
git commit -m "Document factor evaluation metrics"
```
