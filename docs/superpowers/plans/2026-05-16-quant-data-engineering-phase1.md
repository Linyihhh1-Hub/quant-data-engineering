# Quant Data Engineering Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable foundation for the quant data engineering project: package skeleton, dependency config, config loading, Parquet storage, and DWD daily-bar cleaning.

**Architecture:** The project is a local Python package under `src/quant_data`. Each module owns one responsibility: configuration, storage, and cleaning. Tests use deterministic fixture data and never call live network APIs.

**Tech Stack:** Python 3.10+, pandas, pyarrow, pytest, PyYAML.

---

## File Structure

Create these files:

- `pyproject.toml`: package metadata, dependencies, pytest settings.
- `README.md`: first-stage project usage and pipeline overview.
- `configs/data.yaml`: local data paths and cleaning defaults.
- `src/quant_data/__init__.py`: package marker.
- `src/quant_data/config.py`: load YAML config and resolve project paths.
- `src/quant_data/storage/parquet.py`: read/write Parquet helpers.
- `src/quant_data/cleaning/daily.py`: DWD daily market data cleaning logic.
- `tests/conftest.py`: reusable fixture dataframe.
- `tests/test_config.py`: config behavior tests.
- `tests/test_storage_parquet.py`: Parquet storage tests.
- `tests/test_cleaning_daily.py`: daily cleaning tests.

No AkShare ingestion is implemented in Phase 1. That belongs to a later stage after the local pipeline foundation is tested.

---

### Task 1: Project Skeleton and Dependency Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `configs/data.yaml`
- Create: `src/quant_data/__init__.py`

- [ ] **Step 1: Create project metadata**

Create `pyproject.toml` with:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "quant-data-engineering"
version = "0.1.0"
description = "A-share quant factor data engineering pipeline"
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.0",
    "numpy>=1.24",
    "pyarrow>=14.0",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 2: Create config file**

Create `configs/data.yaml` with:

```yaml
paths:
  data_dir: data
  ods_dir: data/ods
  dwd_dir: data/dwd
  ads_dir: data/ads
  reports_dir: data/reports

cleaning:
  abnormal_return_threshold: 0.2
```

- [ ] **Step 3: Create README stub**

Create `README.md` with:

```markdown
# Quant Data Engineering

Local A-share quant data engineering project for building layered market datasets, quality checks, factor tables, and simple backtest datasets.

## Phase 1

Implemented foundation:

- Python package skeleton
- YAML config loading
- Parquet storage helpers
- DWD daily bar cleaning
- Unit tests with fixture data
```

- [ ] **Step 4: Create package marker**

Create `src/quant_data/__init__.py` with:

```python
"""Quant data engineering package."""
```

- [ ] **Step 5: Verify skeleton imports do not run yet**

Run:

```powershell
pytest
```

Expected: pytest reports no tests collected or no test files yet. If dependencies are missing, install with:

```powershell
python -m pip install -e ".[dev]"
```

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml README.md configs src/quant_data/__init__.py
git commit -m "Initialize Python project skeleton"
```

---

### Task 2: Config Loading

**Files:**
- Create: `src/quant_data/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_config.py` with:

```python
from pathlib import Path

from quant_data.config import load_config, project_root, resolve_path


def test_project_root_points_to_repository_root():
    root = project_root()

    assert (root / "pyproject.toml").exists()
    assert root.name == "量化项目"


def test_load_config_reads_data_yaml():
    config = load_config("configs/data.yaml")

    assert config["paths"]["ods_dir"] == "data/ods"
    assert config["cleaning"]["abnormal_return_threshold"] == 0.2


def test_resolve_path_uses_project_root():
    path = resolve_path("data/dwd")

    assert path == project_root() / Path("data/dwd")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
pytest tests/test_config.py -q
```

Expected: FAIL because `quant_data.config` does not exist.

- [ ] **Step 3: Implement config module**

Create `src/quant_data/config.py` with:

```python
from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(path: str | Path) -> Path:
    raw_path = Path(path)
    if raw_path.is_absolute():
        return raw_path
    return project_root() / raw_path


def load_config(path: str | Path = "configs/data.yaml") -> dict[str, Any]:
    config_path = resolve_path(path)
    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a mapping: {config_path}")
    return data
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
pytest tests/test_config.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/quant_data/config.py tests/test_config.py
git commit -m "Add config loading utilities"
```

---

### Task 3: Parquet Storage Helpers

**Files:**
- Create: `src/quant_data/storage/__init__.py`
- Create: `src/quant_data/storage/parquet.py`
- Create: `tests/test_storage_parquet.py`

- [ ] **Step 1: Write failing storage tests**

Create `tests/test_storage_parquet.py` with:

```python
import pandas as pd

from quant_data.storage.parquet import read_parquet, write_parquet


def test_write_parquet_creates_parent_directory(tmp_path):
    frame = pd.DataFrame({"symbol": ["000001.SZ"], "close": [10.5]})
    output_path = tmp_path / "nested" / "daily.parquet"

    write_parquet(frame, output_path)

    assert output_path.exists()


def test_read_parquet_returns_written_frame(tmp_path):
    frame = pd.DataFrame({"symbol": ["000001.SZ"], "close": [10.5]})
    output_path = tmp_path / "daily.parquet"
    write_parquet(frame, output_path)

    result = read_parquet(output_path)

    pd.testing.assert_frame_equal(result, frame)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
pytest tests/test_storage_parquet.py -q
```

Expected: FAIL because `quant_data.storage.parquet` does not exist.

- [ ] **Step 3: Implement Parquet helpers**

Create `src/quant_data/storage/__init__.py` with:

```python
"""Storage helpers."""
```

Create `src/quant_data/storage/parquet.py` with:

```python
from pathlib import Path

import pandas as pd


def write_parquet(frame: pd.DataFrame, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, index=False)
    return output_path


def read_parquet(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(Path(path))
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
pytest tests/test_storage_parquet.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/quant_data/storage tests/test_storage_parquet.py
git commit -m "Add Parquet storage helpers"
```

---

### Task 4: Daily Bar Cleaning

**Files:**
- Create: `src/quant_data/cleaning/__init__.py`
- Create: `src/quant_data/cleaning/daily.py`
- Create: `tests/conftest.py`
- Create: `tests/test_cleaning_daily.py`

- [ ] **Step 1: Write fixture data**

Create `tests/conftest.py` with:

```python
import pandas as pd
import pytest


@pytest.fixture
def raw_daily_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"trade_date": "2024-01-03", "symbol": "000001", "open": "10.0", "high": "10.8", "low": "9.9", "close": "10.5", "volume": "1000", "amount": "10500"},
            {"trade_date": "2024-01-02", "symbol": "000001", "open": "9.8", "high": "10.2", "low": "9.7", "close": "10.0", "volume": "900", "amount": "9000"},
            {"trade_date": "2024-01-02", "symbol": "600000", "open": "8.0", "high": "8.2", "low": "7.9", "close": "8.1", "volume": "1200", "amount": "9720"},
            {"trade_date": "2024-01-03", "symbol": "600000", "open": "8.1", "high": "8.5", "low": "8.0", "close": "8.4", "volume": "1300", "amount": "10920"},
            {"trade_date": "2024-01-03", "symbol": "600000", "open": "8.1", "high": "8.5", "low": "8.0", "close": "8.4", "volume": "1300", "amount": "10920"},
        ]
    )
```

- [ ] **Step 2: Write failing cleaning tests**

Create `tests/test_cleaning_daily.py` with:

```python
import pandas as pd

from quant_data.cleaning.daily import clean_daily_bars


def test_clean_daily_bars_normalizes_types_and_symbols(raw_daily_frame):
    result = clean_daily_bars(raw_daily_frame)

    assert str(result["trade_date"].dtype) == "datetime64[ns]"
    assert result.loc[result["symbol"].str.startswith("000001"), "symbol"].iloc[0] == "000001.SZ"
    assert result.loc[result["symbol"].str.startswith("600000"), "symbol"].iloc[0] == "600000.SH"
    assert pd.api.types.is_float_dtype(result["close"])


def test_clean_daily_bars_sorts_and_deduplicates(raw_daily_frame):
    result = clean_daily_bars(raw_daily_frame)

    assert len(result) == 4
    assert result[["trade_date", "symbol"]].duplicated().sum() == 0
    assert result[["symbol", "trade_date"]].equals(result[["symbol", "trade_date"]].sort_values(["symbol", "trade_date"]).reset_index(drop=True))


def test_clean_daily_bars_computes_return_per_symbol(raw_daily_frame):
    result = clean_daily_bars(raw_daily_frame)
    pingan = result[result["symbol"] == "000001.SZ"].reset_index(drop=True)

    assert pd.isna(pingan.loc[0, "return_1d"])
    assert round(pingan.loc[1, "return_1d"], 6) == 0.05
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
pytest tests/test_cleaning_daily.py -q
```

Expected: FAIL because `quant_data.cleaning.daily` does not exist.

- [ ] **Step 4: Implement daily cleaning**

Create `src/quant_data/cleaning/__init__.py` with:

```python
"""Cleaning functions for market data."""
```

Create `src/quant_data/cleaning/daily.py` with:

```python
import pandas as pd

NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]


def normalize_symbol(symbol: str) -> str:
    value = str(symbol).strip()
    if value.endswith((".SZ", ".SH", ".BJ")):
        return value
    if value.startswith(("0", "3")):
        return f"{value}.SZ"
    if value.startswith("6"):
        return f"{value}.SH"
    if value.startswith(("4", "8")):
        return f"{value}.BJ"
    return value


def clean_daily_bars(frame: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"trade_date", "symbol", *NUMERIC_COLUMNS}
    missing_columns = required_columns - set(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing}")

    result = frame.copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"])
    result["symbol"] = result["symbol"].map(normalize_symbol)

    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    result = result.drop_duplicates(subset=["trade_date", "symbol"], keep="last")
    result = result.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    result["return_1d"] = result.groupby("symbol")["close"].pct_change()
    return result
```

- [ ] **Step 5: Run cleaning tests and full test suite**

Run:

```powershell
pytest tests/test_cleaning_daily.py -q
pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/quant_data/cleaning tests/conftest.py tests/test_cleaning_daily.py
git commit -m "Add daily bar cleaning pipeline"
```

---

### Task 5: Phase 1 Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README with test command**

Append to `README.md`:

```markdown
## Development

Install in editable mode:

```powershell
python -m pip install -e ".[dev]"
```

Run tests:

```powershell
pytest -q
```
```

- [ ] **Step 2: Run full verification**

Run:

```powershell
pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Check Git status**

Run:

```powershell
git status --short
```

Expected: only `README.md` modified.

- [ ] **Step 4: Commit README update**

```powershell
git add README.md
git commit -m "Document phase 1 development workflow"
```
