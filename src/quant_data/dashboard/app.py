import json
from pathlib import Path

import pandas as pd


def _read_parquet_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _read_json_if_exists(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _format_date_range(frame: pd.DataFrame) -> str:
    if frame.empty or "trade_date" not in frame.columns:
        return "-"
    dates = pd.to_datetime(frame["trade_date"]).dropna()
    if dates.empty:
        return "-"
    return f"{dates.min().date()} ~ {dates.max().date()}"


def _latest_trade_date(frame: pd.DataFrame) -> str:
    if frame.empty or "trade_date" not in frame.columns:
        return "-"
    dates = pd.to_datetime(frame["trade_date"]).dropna()
    if dates.empty:
        return "-"
    return str(dates.max().date())


def _status_counts(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty or "status" not in frame.columns:
        return {}
    return {str(key): int(value) for key, value in frame["status"].value_counts().to_dict().items()}


def _failed_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "status" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["status"].astype(str).str.upper() != "SUCCESS"].reset_index(drop=True)


def _quality_failures(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "status" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["status"].astype(str).str.upper() != "PASS"].reset_index(drop=True)


def build_pipeline_summary(data_dir: str | Path = "data") -> dict[str, object]:
    root = Path(data_dir)
    ods = _read_parquet_if_exists(root / "ods" / "stock_daily.parquet")
    dwd = _read_parquet_if_exists(root / "dwd" / "stock_daily.parquet")
    factors = _read_parquet_if_exists(root / "ads" / "factor_wide_daily.parquet")
    ingestion_report = _read_parquet_if_exists(root / "reports" / "ingestion_report.parquet")
    quality_report = _read_parquet_if_exists(root / "reports" / "data_quality_report.parquet")

    quality_counts = _status_counts(quality_report)
    ingestion_counts = _status_counts(ingestion_report)
    symbol_source = ods if not ods.empty else dwd

    return {
        "ods_rows": len(ods),
        "dwd_rows": len(dwd),
        "factor_rows": len(factors),
        "symbol_count": int(symbol_source["symbol"].nunique()) if "symbol" in symbol_source.columns else 0,
        "date_range": _format_date_range(dwd if not dwd.empty else ods),
        "latest_trade_date": _latest_trade_date(dwd if not dwd.empty else ods),
        "ingestion_success_count": ingestion_counts.get("SUCCESS", 0),
        "ingestion_fail_count": sum(
            count for status, count in ingestion_counts.items() if status.upper() != "SUCCESS"
        ),
        "quality_pass_count": quality_counts.get("PASS", 0),
        "quality_fail_count": sum(count for status, count in quality_counts.items() if status.upper() != "PASS"),
        "failed_symbols": _failed_rows(ingestion_report),
        "failed_quality_rules": _quality_failures(quality_report),
    }


def list_available_factors(data_dir: str | Path = "data") -> list[str]:
    root = Path(data_dir)
    factors = []
    for path in sorted((root / "ads").glob("factor_eval_*.parquet")):
        factors.append(path.stem.removeprefix("factor_eval_"))
    return factors


def build_factor_summary(data_dir: str | Path, factor_name: str) -> dict[str, object]:
    root = Path(data_dir)
    evaluation = _read_parquet_if_exists(root / "ads" / f"factor_eval_{factor_name}.parquet")
    if evaluation.empty:
        return {
            "evaluation": evaluation,
            "ic_mean": 0.0,
            "rank_ic_mean": 0.0,
            "positive_ic_ratio": 0.0,
            "icir": 0.0,
        }

    ic = evaluation["ic"].dropna() if "ic" in evaluation.columns else pd.Series(dtype="float64")
    rank_ic = evaluation["rank_ic"].dropna() if "rank_ic" in evaluation.columns else pd.Series(dtype="float64")
    ic_std = ic.std(ddof=1)

    return {
        "evaluation": evaluation.sort_values("trade_date").reset_index(drop=True),
        "ic_mean": float(ic.mean()) if not ic.empty else 0.0,
        "rank_ic_mean": float(rank_ic.mean()) if not rank_ic.empty else 0.0,
        "positive_ic_ratio": float((ic > 0).mean()) if not ic.empty else 0.0,
        "icir": float(ic.mean() / ic_std) if len(ic) > 1 and ic_std != 0 else 0.0,
    }


def build_backtest_summary(data_dir: str | Path, factor_name: str) -> dict[str, object]:
    root = Path(data_dir)
    daily = _read_parquet_if_exists(root / "ads" / f"backtest_daily_{factor_name}.parquet")
    metrics = _read_json_if_exists(root / "ads" / f"backtest_metrics_{factor_name}.json")
    if not daily.empty and "trade_date" in daily.columns:
        daily = daily.sort_values("trade_date").reset_index(drop=True)
    return {"daily": daily, "metrics": metrics}


def _format_percent(value: object) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "-"


def _format_number(value: object) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "-"


def _metric_row(st, items: list[tuple[str, object, str]]) -> None:
    columns = st.columns(len(items))
    for column, (label, value, kind) in zip(columns, items):
        if kind == "percent":
            display_value = _format_percent(value)
        elif kind == "number":
            display_value = _format_number(value)
        else:
            display_value = str(value)
        column.metric(label, display_value)


def render_pipeline_tab(st, data_dir: Path) -> None:
    summary = build_pipeline_summary(data_dir)
    _metric_row(
        st,
        [
            ("股票数量", summary["symbol_count"], "text"),
            ("日期范围", summary["date_range"], "text"),
            ("最新交易日", summary["latest_trade_date"], "text"),
            (
                "采集状态",
                f'{summary["ingestion_success_count"]} 成功 / {summary["ingestion_fail_count"]} 失败',
                "text",
            ),
            (
                "质量规则",
                f'{summary["quality_pass_count"]} PASS / {summary["quality_fail_count"]} FAIL',
                "text",
            ),
        ],
    )
    _metric_row(
        st,
        [
            ("ODS 行数", summary["ods_rows"], "text"),
            ("DWD 行数", summary["dwd_rows"], "text"),
            ("ADS 因子宽表行数", summary["factor_rows"], "text"),
        ],
    )

    st.subheader("失败股票列表")
    failed_symbols = summary["failed_symbols"]
    if failed_symbols.empty:
        st.info("当前没有失败股票。")
    else:
        columns = [column for column in ["symbol", "status", "row_count", "message"] if column in failed_symbols.columns]
        st.dataframe(failed_symbols[columns], use_container_width=True, hide_index=True)

    st.subheader("质量异常规则")
    failed_quality_rules = summary["failed_quality_rules"]
    if failed_quality_rules.empty:
        st.info("当前没有质量异常规则。")
    else:
        columns = [
            column
            for column in ["rule_name", "status", "failed_count", "failed_sample"]
            if column in failed_quality_rules.columns
        ]
        st.dataframe(failed_quality_rules[columns], use_container_width=True, hide_index=True)


def render_factor_tab(st, data_dir: Path, factor_name: str) -> None:
    summary = build_factor_summary(data_dir, factor_name)
    evaluation = summary["evaluation"]
    _metric_row(
        st,
        [
            ("IC 均值", summary["ic_mean"], "number"),
            ("RankIC 均值", summary["rank_ic_mean"], "number"),
            ("正 IC 占比", summary["positive_ic_ratio"], "percent"),
            ("ICIR", summary["icir"], "number"),
        ],
    )
    if evaluation.empty:
        st.warning("未找到该因子的评估结果。")
        return

    chart_frame = evaluation.set_index("trade_date")
    st.subheader("IC / RankIC 曲线")
    st.line_chart(chart_frame[[column for column in ["ic", "rank_ic"] if column in chart_frame.columns]])

    st.subheader("分组收益")
    group_columns = [
        column
        for column in ["top_group_return", "bottom_group_return", "long_short_return"]
        if column in evaluation.columns
    ]
    if group_columns:
        group_returns = evaluation[group_columns].mean().rename(
            {
                "top_group_return": "Top 组",
                "bottom_group_return": "Bottom 组",
                "long_short_return": "Top-Bottom",
            }
        )
        st.bar_chart(group_returns)
    else:
        st.info("评估结果中没有分组收益字段。")


def render_backtest_tab(st, data_dir: Path, factor_name: str) -> None:
    summary = build_backtest_summary(data_dir, factor_name)
    daily = summary["daily"]
    metrics = summary["metrics"]
    _metric_row(
        st,
        [
            ("累计收益", metrics.get("total_return"), "percent"),
            ("年化收益", metrics.get("annualized_return"), "percent"),
            ("夏普比率", metrics.get("sharpe"), "number"),
            ("最大回撤", metrics.get("max_drawdown"), "percent"),
            ("换手", metrics.get("turnover"), "number"),
        ],
    )
    if daily.empty:
        st.warning("未找到该因子的回测结果。")
        return

    chart_frame = daily.set_index("trade_date")
    st.subheader("策略净值 vs 基准净值")
    st.line_chart(chart_frame[[column for column in ["portfolio_value", "benchmark_value"] if column in chart_frame.columns]])

    st.subheader("回撤曲线")
    if "drawdown" in chart_frame.columns:
        st.line_chart(chart_frame[["drawdown"]])
    else:
        st.info("回测结果中没有 drawdown 字段。")

    if "target_exposure" in chart_frame.columns:
        st.subheader("情绪择时仓位")
        st.line_chart(chart_frame[["target_exposure"]])


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="量化数据工程看板", layout="wide")
    st.title("量化数据工程看板")

    data_dir = Path(st.sidebar.text_input("数据目录", value="data"))
    factors = list_available_factors(data_dir)
    if not factors:
        st.warning("未找到因子评估文件，请先运行数据流水线。")
        return
    factor_name = st.sidebar.selectbox("因子", factors, index=0)

    tabs = st.tabs(["数据链路概览", "因子有效性评估", "策略回测表现"])
    with tabs[0]:
        render_pipeline_tab(st, data_dir)
    with tabs[1]:
        render_factor_tab(st, data_dir, factor_name)
    with tabs[2]:
        render_backtest_tab(st, data_dir, factor_name)


if __name__ == "__main__":
    main()
