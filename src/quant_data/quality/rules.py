import pandas as pd

REQUIRED_FIELDS = ["open", "high", "low", "close", "volume"]
REPORT_COLUMNS = ["rule_name", "status", "failed_count", "failed_sample"]


def _sample(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    # 质量报告只保留少量失败样例，避免真实数据下报告字段过大。
    return frame.head(5).to_dict(orient="records").__repr__()


def build_result(rule_name: str, failed: pd.DataFrame) -> dict[str, object]:
    failed_count = len(failed)
    return {
        "rule_name": rule_name,
        "status": "PASS" if failed_count == 0 else "FAIL",
        "failed_count": failed_count,
        "failed_sample": _sample(failed),
    }


def _duplicate_primary_keys(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame.duplicated(subset=["trade_date", "symbol"], keep=False)]


def _null_required_fields(frame: pd.DataFrame) -> pd.DataFrame:
    mask = frame[REQUIRED_FIELDS].isna().any(axis=1)
    failed = frame.loc[mask, ["trade_date", "symbol", *REQUIRED_FIELDS]].copy()
    if failed.empty:
        failed["null_fields"] = pd.Series(dtype=str)
        return failed
    failed["null_fields"] = frame.loc[mask, REQUIRED_FIELDS].isna().apply(
        lambda row: ",".join(row.index[row]), axis=1
    )
    return failed


def _invalid_prices(frame: pd.DataFrame) -> pd.DataFrame:
    mask = (
        (frame["open"] < 0)
        | (frame["high"] < 0)
        | (frame["low"] < 0)
        | (frame["close"] <= 0)
        | (frame["high"] < frame["low"])
    )
    return frame.loc[mask, ["trade_date", "symbol", "open", "high", "low", "close"]]


def _invalid_volume(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[frame["volume"] < 0, ["trade_date", "symbol", "volume"]]


def _incomplete_dates(frame: pd.DataFrame, min_rows_per_date: int) -> pd.DataFrame:
    counts = frame.groupby("trade_date").size().reset_index(name="row_count")
    return counts[counts["row_count"] < min_rows_per_date]


def _abnormal_returns(frame: pd.DataFrame, threshold: float) -> pd.DataFrame:
    mask = frame["return_1d"].abs() > threshold
    return frame.loc[mask, ["trade_date", "symbol", "return_1d"]]


def run_quality_checks(
    frame: pd.DataFrame,
    min_rows_per_date: int = 1,
    abnormal_return_threshold: float = 0.2,
) -> pd.DataFrame:
    # 每条规则都返回统一结构，方便后续落表、告警或接入调度系统。
    results = [
        build_result("primary_key_unique", _duplicate_primary_keys(frame)),
        build_result("required_fields_not_null", _null_required_fields(frame)),
        build_result("price_valid", _invalid_prices(frame)),
        build_result("volume_valid", _invalid_volume(frame)),
        build_result("date_completeness", _incomplete_dates(frame, min_rows_per_date)),
        build_result("abnormal_return", _abnormal_returns(frame, abnormal_return_threshold)),
    ]
    return pd.DataFrame(results, columns=REPORT_COLUMNS)
