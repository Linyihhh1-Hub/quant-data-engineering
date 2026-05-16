from pathlib import Path

import pandas as pd


def write_parquet(frame: pd.DataFrame, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output_path, index=False)
    return output_path


def read_parquet(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(Path(path))
