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
