# Quant Data Engineering Phase 2 Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic data quality checks for cleaned daily market data.

**Architecture:** Quality rules live in `src/quant_data/quality/rules.py` and return a normalized pandas DataFrame report. The module does not read or write files directly; storage remains the responsibility of `quant_data.storage`.

**Tech Stack:** Python 3.10+, pandas, pytest.

---

## File Structure

Create these files:

- `src/quant_data/quality/__init__.py`: package marker.
- `src/quant_data/quality/rules.py`: data quality checks and report generation.
- `tests/test_quality_rules.py`: unit tests for all MVP quality rules.

Modify:

- `README.md`: add Phase 2 quality module summary.

---

## Report Contract

`run_quality_checks(frame, min_rows_per_date=1, abnormal_return_threshold=0.2)` returns a DataFrame with these columns:

```text
rule_name, status, failed_count, failed_sample
```

`status` is `PASS` when `failed_count == 0`, otherwise `FAIL`.

Rules implemented in Phase 2:

1. `primary_key_unique`: `trade_date + symbol` has no duplicates.
2. `required_fields_not_null`: `open`, `high`, `low`, `close`, `volume` are not null.
3. `price_valid`: prices are non-negative, `close > 0`, and `high >= low`.
4. `volume_valid`: `volume >= 0`.
5. `date_completeness`: every trade date has at least `min_rows_per_date` rows.
6. `abnormal_return`: absolute `return_1d` above threshold is reported.

---

## Tasks

### Task 1: Write Failing Quality Tests

**Files:**
- Create: `tests/test_quality_rules.py`

Write tests that construct small DataFrames in memory and assert each rule reports `PASS` or `FAIL` correctly. Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_quality_rules.py -q
```

Expected: FAIL because `quant_data.quality.rules` does not exist.

### Task 2: Implement Quality Module

**Files:**
- Create: `src/quant_data/quality/__init__.py`
- Create: `src/quant_data/quality/rules.py`

Implement:

- `build_result(rule_name: str, failed: pd.DataFrame) -> dict[str, object]`
- `run_quality_checks(frame: pd.DataFrame, min_rows_per_date: int = 1, abnormal_return_threshold: float = 0.2) -> pd.DataFrame`

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_quality_rules.py -q
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
git add src/quant_data/quality tests/test_quality_rules.py
git commit -m "Add daily data quality checks"
```

### Task 4: Update README

Append a Phase 2 section summarizing data quality checks and the report contract.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

Commit:

```powershell
git add README.md
git commit -m "Document data quality checks"
```
