from pathlib import Path

import pandas as pd


def load_symbols(path: str | Path) -> list[str]:
    frame = pd.read_csv(path, dtype={"symbol": "string"})
    if "symbol" not in frame.columns:
        raise ValueError("Symbol file must contain a 'symbol' column")

    symbols = []
    seen = set()
    for value in frame["symbol"].dropna():
        symbol = str(value).strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols
