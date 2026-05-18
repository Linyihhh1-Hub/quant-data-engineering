import pandas as pd

from quant_data.ingestion.symbols import load_symbols


def test_load_symbols_reads_symbol_column_and_preserves_order(tmp_path):
    path = tmp_path / "symbols.csv"
    pd.DataFrame({"symbol": ["000001", "600000", "000001", None, " 600519 "]}).to_csv(
        path, index=False
    )

    result = load_symbols(path)

    assert result == ["000001", "600000", "600519"]


def test_load_symbols_raises_when_symbol_column_missing(tmp_path):
    path = tmp_path / "symbols.csv"
    pd.DataFrame({"code": ["000001"]}).to_csv(path, index=False)

    try:
        load_symbols(path)
    except ValueError as error:
        assert "symbol" in str(error)
    else:
        raise AssertionError("Expected ValueError")
