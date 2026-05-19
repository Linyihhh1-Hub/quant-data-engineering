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
    return {str(key).upper(): int(value) for key, value in frame["status"].value_counts().to_dict().items()}


def _abnormal_ingestion_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "status" not in frame.columns:
        return pd.DataFrame()
    normal_statuses = {"SUCCESS", "SKIPPED"}
    return frame[~frame["status"].astype(str).str.upper().isin(normal_statuses)].reset_index(drop=True)


def _normalize_symbol_values(series: pd.Series) -> set[str]:
    return {str(symbol).split(".")[0] for symbol in series.dropna().unique()}


def _filter_ingestion_for_current_symbols(ingestion_report: pd.DataFrame, symbol_source: pd.DataFrame) -> pd.DataFrame:
    if ingestion_report.empty or symbol_source.empty:
        return ingestion_report
    if "symbol" not in ingestion_report.columns or "symbol" not in symbol_source.columns:
        return ingestion_report
    current_symbols = _normalize_symbol_values(symbol_source["symbol"])
    result = ingestion_report.copy()
    normalized_report_symbols = result["symbol"].astype(str).str.split(".").str[0]
    return result[normalized_report_symbols.isin(current_symbols)].reset_index(drop=True)


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
    symbol_source = ods if not ods.empty else dwd
    current_ingestion_report = _filter_ingestion_for_current_symbols(ingestion_report, symbol_source)
    ingestion_counts = _status_counts(current_ingestion_report)
    ingestion_total = sum(ingestion_counts.values())
    ingestion_success_count = ingestion_counts.get("SUCCESS", 0)
    ingestion_skipped_count = ingestion_counts.get("SKIPPED", 0)
    ingestion_normal_count = ingestion_success_count + ingestion_skipped_count
    ingestion_abnormal_count = sum(
        count for status, count in ingestion_counts.items() if status not in {"SUCCESS", "SKIPPED"}
    )

    return {
        "ods_rows": len(ods),
        "dwd_rows": len(dwd),
        "factor_rows": len(factors),
        "symbol_count": int(symbol_source["symbol"].nunique()) if "symbol" in symbol_source.columns else 0,
        "date_range": _format_date_range(dwd if not dwd.empty else ods),
        "latest_trade_date": _latest_trade_date(dwd if not dwd.empty else ods),
        "ingestion_total": ingestion_total,
        "ingestion_success_count": ingestion_success_count,
        "ingestion_skipped_count": ingestion_skipped_count,
        "ingestion_abnormal_count": ingestion_abnormal_count,
        "ingestion_normal_rate": ingestion_normal_count / ingestion_total if ingestion_total else 0.0,
        "quality_pass_count": quality_counts.get("PASS", 0),
        "quality_fail_count": sum(count for status, count in quality_counts.items() if status != "PASS"),
        "abnormal_symbols": _abnormal_ingestion_rows(ingestion_report),
        "failed_quality_rules": _quality_failures(quality_report),
    }


def list_available_factors(data_dir: str | Path = "data") -> list[str]:
    root = Path(data_dir)
    factors = []
    for path in sorted((root / "ads").glob("factor_eval_*.parquet")):
        factors.append(path.stem.removeprefix("factor_eval_"))
    return factors


def default_factor_index(factors: list[str]) -> int:
    for preferred in ["momentum_20d_zscore", "momentum_20d"]:
        if preferred in factors:
            return factors.index(preferred)
    return 0


def build_factor_comparison(data_dir: str | Path = "data") -> pd.DataFrame:
    rows = []
    for factor_name in list_available_factors(data_dir):
        factor_summary = build_factor_summary(data_dir, factor_name)
        backtest_summary = build_backtest_summary(data_dir, factor_name)
        metrics = backtest_summary["metrics"]
        rows.append(
            {
                "factor_name": factor_name,
                "factor_direction": metrics.get("factor_direction", "top"),
                "top_quantile": float(metrics.get("top_quantile", 0.0)),
                "rebalance_interval": int(metrics.get("rebalance_interval", 0)),
                "ic_mean": factor_summary["ic_mean"],
                "rank_ic_mean": factor_summary["rank_ic_mean"],
                "positive_ic_ratio": factor_summary["positive_ic_ratio"],
                "icir": factor_summary["icir"],
                "total_return": float(metrics.get("total_return", 0.0)),
                "benchmark_total_return": backtest_summary["benchmark_total_return"],
                "excess_return": backtest_summary["excess_return"],
                "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
                "sharpe": float(metrics.get("sharpe", 0.0)),
                "turnover": float(metrics.get("turnover", 0.0)),
                "total_cost": float(metrics.get("total_cost", 0.0)),
                "cost_drag": float(metrics.get("cost_drag", 0.0)),
                "cost_to_return": float(metrics.get("cost_to_return", metrics.get("cost_return_ratio", 0.0))),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["sharpe", "excess_return"], ascending=[False, False]).reset_index(drop=True)


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
            "interpretation": "未找到该因子的评估结果，暂时无法判断因子有效性。",
        }

    ic = evaluation["ic"].dropna() if "ic" in evaluation.columns else pd.Series(dtype="float64")
    rank_ic = evaluation["rank_ic"].dropna() if "rank_ic" in evaluation.columns else pd.Series(dtype="float64")
    ic_std = ic.std(ddof=1)

    ic_mean = float(ic.mean()) if not ic.empty else 0.0
    rank_ic_mean = float(rank_ic.mean()) if not rank_ic.empty else 0.0
    positive_ic_ratio = float((ic > 0).mean()) if not ic.empty else 0.0
    return {
        "evaluation": evaluation.sort_values("trade_date").reset_index(drop=True),
        "ic_mean": ic_mean,
        "rank_ic_mean": rank_ic_mean,
        "positive_ic_ratio": positive_ic_ratio,
        "icir": float(ic.mean() / ic_std) if len(ic) > 1 and ic_std != 0 else 0.0,
        "interpretation": interpret_factor_strength(ic_mean, rank_ic_mean, positive_ic_ratio),
    }


def build_yearly_summary(data_dir: str | Path, factor_name: str) -> pd.DataFrame:
    root = Path(data_dir)
    yearly = _read_parquet_if_exists(root / "ads" / "factor_yearly_summary.parquet")
    if yearly.empty or "factor_name" not in yearly.columns:
        return pd.DataFrame()
    return yearly[yearly["factor_name"] == factor_name].sort_values("year").reset_index(drop=True)


def build_rolling_summary(data_dir: str | Path, factor_name: str) -> pd.DataFrame:
    root = Path(data_dir)
    rolling = _read_parquet_if_exists(root / "ads" / "factor_rolling_summary.parquet")
    if rolling.empty or "factor_name" not in rolling.columns:
        return pd.DataFrame()
    result = rolling[rolling["factor_name"] == factor_name].copy()
    if "trade_date" in result.columns:
        result["trade_date"] = pd.to_datetime(result["trade_date"])
        result = result.sort_values("trade_date")
    return result.reset_index(drop=True)


def build_parameter_sensitivity(data_dir: str | Path, factor_name: str) -> pd.DataFrame:
    root = Path(data_dir)
    sensitivity = _read_parquet_if_exists(root / "ads" / "parameter_sensitivity.parquet")
    if sensitivity.empty or "factor_name" not in sensitivity.columns:
        return pd.DataFrame()
    result = sensitivity[sensitivity["factor_name"] == factor_name].copy()
    sort_columns = [column for column in ["sharpe", "excess_return", "max_drawdown", "turnover"] if column in result.columns]
    if sort_columns:
        ascending = [False if column != "turnover" else True for column in sort_columns]
        result = result.sort_values(sort_columns, ascending=ascending)
    return result.head(20).reset_index(drop=True)


def build_cost_sensitivity(data_dir: str | Path, factor_name: str) -> pd.DataFrame:
    root = Path(data_dir)
    sensitivity = _read_parquet_if_exists(root / "ads" / "cost_sensitivity.parquet")
    if sensitivity.empty or "factor_name" not in sensitivity.columns:
        return pd.DataFrame()
    return sensitivity[sensitivity["factor_name"] == factor_name].reset_index(drop=True)


def interpret_factor_strength(ic_mean: float, rank_ic_mean: float, positive_ic_ratio: float) -> str:
    if abs(ic_mean) < 0.02 and abs(rank_ic_mean) < 0.02:
        return (
            f"当前因子 IC 均值为 {ic_mean:.4f}，RankIC 均值为 {rank_ic_mean:.4f}，"
            f"正 IC 占比为 {positive_ic_ratio:.2%}，整体截面预测能力较弱，不能认为具有稳定有效性。"
        )
    if ic_mean > 0 and rank_ic_mean > 0 and positive_ic_ratio >= 0.55:
        return (
            f"当前因子 IC 均值为 {ic_mean:.4f}，RankIC 均值为 {rank_ic_mean:.4f}，"
            f"正 IC 占比为 {positive_ic_ratio:.2%}，在当前样本内体现出一定选股解释力。"
        )
    return (
        f"当前因子 IC 均值为 {ic_mean:.4f}，RankIC 均值为 {rank_ic_mean:.4f}，"
        f"正 IC 占比为 {positive_ic_ratio:.2%}，信号方向不够稳定，建议结合更长区间和更多因子交叉验证。"
    )


def estimate_unscaled_strategy_value(daily: pd.DataFrame) -> pd.Series:
    if daily.empty or "daily_return" not in daily.columns:
        return pd.Series(dtype="float64")
    exposure = daily.get("target_exposure", pd.Series(1.0, index=daily.index)).replace(0, pd.NA)
    raw_return = daily["daily_return"].fillna(0.0).div(exposure).fillna(0.0)
    if not raw_return.empty:
        raw_return.iloc[0] = 0.0
    return (1 + raw_return).cumprod()


def build_backtest_summary(data_dir: str | Path, factor_name: str) -> dict[str, object]:
    root = Path(data_dir)
    daily = _read_parquet_if_exists(root / "ads" / f"backtest_daily_{factor_name}.parquet")
    metrics = _read_json_if_exists(root / "ads" / f"backtest_metrics_{factor_name}.json")
    if not daily.empty and "trade_date" in daily.columns:
        daily = daily.sort_values("trade_date").reset_index(drop=True)
    if not daily.empty:
        unscaled = estimate_unscaled_strategy_value(daily)
        if not unscaled.empty:
            daily = daily.copy()
            daily["unscaled_portfolio_value"] = unscaled
    benchmark_total_return = (
        float(daily["benchmark_value"].iloc[-1] - 1)
        if not daily.empty and "benchmark_value" in daily.columns
        else 0.0
    )
    hs300_total_return = (
        float(daily["hs300_benchmark_value"].iloc[-1] - 1)
        if not daily.empty and "hs300_benchmark_value" in daily.columns
        else 0.0
    )
    total_return = float(metrics.get("total_return", 0.0))
    return {
        "daily": daily,
        "metrics": metrics,
        "benchmark_total_return": benchmark_total_return,
        "excess_return": total_return - benchmark_total_return,
        "hs300_total_return": hs300_total_return,
        "hs300_excess_return": total_return - hs300_total_return,
        "cost_assumptions": {
            "commission_rate": 0.0003,
            "stamp_tax_rate": 0.0005,
            "slippage_rate": 0.0005,
        },
    }


def _format_metric_int(value: object) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "-"


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
    st.write(f"日期范围：{summary['date_range']}")
    st.write(f"最新交易日：{summary['latest_trade_date']}")
    _metric_row(
        st,
        [
            ("股票数", summary["symbol_count"], "text"),
            (
                "链路正常率",
                _format_percent(summary["ingestion_normal_rate"]),
                "text",
            ),
            (
                "质量状态",
                f'{summary["quality_pass_count"]} / {summary["quality_pass_count"] + summary["quality_fail_count"]} 通过',
                "text",
            ),
        ],
    )
    _metric_row(
        st,
        [
            ("成功", _format_metric_int(summary["ingestion_success_count"]), "text"),
            ("跳过", _format_metric_int(summary["ingestion_skipped_count"]), "text"),
            ("异常", _format_metric_int(summary["ingestion_abnormal_count"]), "text"),
        ],
    )
    st.caption("采集状态依次为：成功 / 跳过 / 异常。SKIPPED 表示本地数据已覆盖目标起止日期范围，本次增量采集跳过，不代表采集失败。")
    _metric_row(
        st,
        [
            ("ODS", _format_metric_int(summary["ods_rows"]), "text"),
            ("DWD", _format_metric_int(summary["dwd_rows"]), "text"),
            ("ADS 因子", _format_metric_int(summary["factor_rows"]), "text"),
        ],
    )

    st.subheader("采集异常 / 空返回列表")
    abnormal_symbols = summary["abnormal_symbols"]
    if abnormal_symbols.empty:
        st.info("当前没有采集异常或空返回。")
    else:
        columns = [column for column in ["symbol", "status", "row_count", "message"] if column in abnormal_symbols.columns]
        st.dataframe(abnormal_symbols[columns], use_container_width=True, hide_index=True)

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
    comparison = build_factor_comparison(data_dir)
    if not comparison.empty:
        st.subheader("多因子对比")
        display = comparison.copy()
        percent_columns = [
            "positive_ic_ratio",
            "total_return",
            "benchmark_total_return",
            "excess_return",
            "max_drawdown",
            "total_cost",
            "cost_drag",
            "cost_to_return",
        ]
        for column in percent_columns:
            if column in display.columns:
                display[column] = display[column].map(_format_percent)
        for column in ["top_quantile", "ic_mean", "rank_ic_mean", "icir", "sharpe", "turnover"]:
            if column in display.columns:
                display[column] = display[column].map(_format_number)
        columns = [
            column
            for column in [
                "factor_name",
                "factor_direction",
                "top_quantile",
                "rebalance_interval",
                "ic_mean",
                "rank_ic_mean",
                "positive_ic_ratio",
                "icir",
                "total_return",
                "excess_return",
                "max_drawdown",
                "sharpe",
                "turnover",
                "total_cost",
                "cost_drag",
                "cost_to_return",
            ]
            if column in display.columns
        ]
        st.dataframe(display[columns], use_container_width=True, hide_index=True)

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
    st.info(summary["interpretation"])

    chart_frame = evaluation.set_index("trade_date")
    st.subheader("IC / RankIC 曲线")
    st.line_chart(chart_frame[[column for column in ["ic", "rank_ic"] if column in chart_frame.columns]])

    st.subheader("Top / Bottom / Long-Short 平均收益")
    group_columns = [
        column
        for column in ["top_group_return", "bottom_group_return", "long_short_return"]
        if column in evaluation.columns
    ]
    if group_columns:
        group_returns = pd.Series(
            {
                "Top组": evaluation["top_group_return"].mean(),
                "Bottom组": evaluation["bottom_group_return"].mean(),
                "Top-Bottom": evaluation["long_short_return"].mean(),
            }
        )
        st.bar_chart(group_returns)
    else:
        st.info("评估结果中没有分组收益字段。")

    yearly = build_yearly_summary(data_dir, factor_name)
    st.subheader("年度表现")
    if yearly.empty:
        st.info("未找到年度表现汇总，请先运行 factor-suite 或 stability 命令。")
    else:
        display = yearly.copy()
        percent_columns = [
            "positive_ic_ratio",
            "total_return",
            "benchmark_total_return",
            "excess_return",
            "max_drawdown",
        ]
        for column in percent_columns:
            if column in display.columns:
                display[column] = display[column].map(_format_percent)
        for column in ["ic_mean", "rank_ic_mean", "icir", "sharpe", "turnover", "full_period_turnover"]:
            if column in display.columns:
                display[column] = display[column].map(_format_number)
        st.dataframe(display, use_container_width=True, hide_index=True)

    rolling = build_rolling_summary(data_dir, factor_name)
    st.subheader("滚动稳定性")
    if rolling.empty:
        st.info("未找到滚动稳定性汇总，请先运行 factor-suite 或 stability 命令。")
    else:
        chart_frame = rolling.set_index("trade_date")
        columns = [
            column
            for column in [
                "rolling_60d_rank_ic_mean",
                "rolling_120d_excess_return",
                "rolling_120d_max_drawdown",
            ]
            if column in chart_frame.columns
        ]
        st.line_chart(chart_frame[columns])


def render_backtest_tab(st, data_dir: Path, factor_name: str) -> None:
    summary = build_backtest_summary(data_dir, factor_name)
    daily = summary["daily"]
    metrics = summary["metrics"]
    st.info(
        "策略诊断需要同时看：是否跑赢沪深300、是否跑赢股票池等权基准、成本前后收益差异、"
        "换手率与成本侵蚀、最大回撤和 Sharpe。"
    )
    _metric_row(
        st,
        [
            ("策略累计", metrics.get("total_return"), "percent"),
            ("等权基准", summary["benchmark_total_return"], "percent"),
            ("沪深300", summary["hs300_total_return"], "percent"),
            ("指数超额", summary["hs300_excess_return"], "percent"),
            ("最大回撤", metrics.get("max_drawdown"), "percent"),
            ("Sharpe", metrics.get("sharpe"), "number"),
        ],
    )
    _metric_row(st, [("换手", metrics.get("turnover"), "number"), ("平均仓位", metrics.get("average_exposure"), "percent")])
    _metric_row(
        st,
        [
            ("成本前累计", metrics.get("gross_total_return"), "percent"),
            ("成本侵蚀", metrics.get("cost_drag"), "percent"),
            ("成本/收益", metrics.get("cost_to_return", metrics.get("cost_return_ratio")), "percent"),
        ],
    )
    costs = summary["cost_assumptions"]
    st.caption(
        "成本假设："
        f"佣金 {_format_percent(costs['commission_rate'])}，"
        f"印花税 {_format_percent(costs['stamp_tax_rate'])}，"
        f"滑点 {_format_percent(costs['slippage_rate'])}"
    )
    if daily.empty:
        st.warning("未找到该因子的回测结果。")
        return

    chart_frame = daily.set_index("trade_date")
    st.subheader("策略净值对比")
    net_value_columns = [
        column
        for column in [
            "gross_portfolio_value",
            "unscaled_portfolio_value",
            "portfolio_value",
            "benchmark_value",
            "hs300_benchmark_value",
        ]
        if column in chart_frame.columns
    ]
    net_value = chart_frame[net_value_columns].rename(
        columns={
            "gross_portfolio_value": "成本前策略净值",
            "unscaled_portfolio_value": "未择时估算净值",
            "portfolio_value": "成本后策略净值",
            "benchmark_value": "等权基准净值",
            "hs300_benchmark_value": "沪深300净值",
        }
    )
    st.line_chart(net_value)
    st.caption("净值图包含：成本前策略净值、成本后策略净值、等权基准净值、沪深300净值，用于观察成本侵蚀和指数超额。")

    st.subheader("回撤曲线")
    if "drawdown" in chart_frame.columns:
        st.line_chart(chart_frame[["drawdown"]])
    else:
        st.info("回测结果中没有 drawdown 字段。")

    if "target_exposure" in chart_frame.columns:
        st.subheader("情绪择时仓位")
        exposure_columns = [column for column in ["raw_target_exposure", "target_exposure"] if column in chart_frame.columns]
        exposure_chart = chart_frame[exposure_columns].rename(
            columns={"raw_target_exposure": "平滑前目标仓位", "target_exposure": "实际目标仓位"}
        )
        st.line_chart(exposure_chart)

    st.subheader("参数敏感性")
    sensitivity = build_parameter_sensitivity(data_dir, factor_name)
    if sensitivity.empty:
        available = _read_parquet_if_exists(Path(data_dir) / "ads" / "parameter_sensitivity.parquet")
        if available.empty or "factor_name" not in available.columns:
            st.info("未找到参数敏感性结果，请先运行 sensitivity 或 run-all 命令。")
        else:
            names = ", ".join(sorted(available["factor_name"].dropna().astype(str).unique()))
            st.info(f"当前因子没有参数敏感性结果。已有结果因子：{names}")
    else:
        display = sensitivity.copy()
        percent_columns = [
            "total_return",
            "gross_total_return",
            "benchmark_total_return",
            "index_total_return",
            "excess_return",
            "index_excess_return",
            "max_drawdown",
            "total_cost",
            "cost_drag",
            "cost_to_return",
        ]
        for column in percent_columns:
            if column in display.columns:
                display[column] = display[column].map(_format_percent)
        for column in ["top_quantile", "rebalance_interval", "sharpe", "turnover"]:
            if column in display.columns:
                display[column] = display[column].map(_format_number)
        columns = [
            column
            for column in [
                "factor_name",
                "factor_direction",
                "top_quantile",
                "rebalance_interval",
                "total_return",
                "excess_return",
                "max_drawdown",
                "sharpe",
                "turnover",
                "total_cost",
            ]
            if column in display.columns
        ]
        st.caption("默认展示按 Sharpe、超额收益、回撤、换手排序后的 Top 20 参数组合。")
        st.dataframe(display[columns], use_container_width=True, hide_index=True)

    st.subheader("成本敏感性")
    cost_sensitivity = build_cost_sensitivity(data_dir, factor_name)
    if cost_sensitivity.empty:
        st.info("未找到成本敏感性结果，请先运行 cost-sensitivity 或 run-all 命令。")
    else:
        chart_columns = [column for column in ["cost_scenario", "total_return"] if column in cost_sensitivity.columns]
        if len(chart_columns) == 2:
            st.bar_chart(cost_sensitivity.set_index("cost_scenario")[["total_return"]])
        display = cost_sensitivity.copy()
        percent_columns = [
            "commission",
            "stamp_tax",
            "slippage",
            "total_return",
            "before_cost_total_return",
            "cost_drag",
            "cost_to_return",
            "max_drawdown",
        ]
        for column in percent_columns:
            if column in display.columns:
                display[column] = display[column].map(_format_percent)
        for column in ["sharpe", "turnover"]:
            if column in display.columns:
                display[column] = display[column].map(_format_number)
        columns = [
            column
            for column in [
                "factor_name",
                "factor_direction",
                "cost_scenario",
                "commission",
                "stamp_tax",
                "slippage",
                "total_return",
                "before_cost_total_return",
                "cost_drag",
                "cost_to_return",
                "sharpe",
                "turnover",
            ]
            if column in display.columns
        ]
        st.dataframe(display[columns], use_container_width=True, hide_index=True)


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="量化数据工程看板", layout="wide")
    st.title("量化数据工程看板")

    data_dir = Path(st.sidebar.text_input("数据目录", value="data"))
    factors = list_available_factors(data_dir)
    if not factors:
        st.warning("未找到因子评估文件，请先运行数据流水线。")
        return
    factor_name = st.sidebar.selectbox("因子", factors, index=default_factor_index(factors))

    tabs = st.tabs(["数据链路概览", "因子有效性评估", "策略回测表现"])
    with tabs[0]:
        render_pipeline_tab(st, data_dir)
    with tabs[1]:
        render_factor_tab(st, data_dir, factor_name)
    with tabs[2]:
        render_backtest_tab(st, data_dir, factor_name)


if __name__ == "__main__":
    main()
