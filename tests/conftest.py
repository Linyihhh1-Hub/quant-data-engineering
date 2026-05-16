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
