import argparse
import json
from pathlib import Path

from quant_data.backtest.simple import run_simple_backtest
from quant_data.cleaning.daily import clean_daily_bars
from quant_data.dimensions.market import write_hs300_symbol_pool
from quant_data.dimensions.market import write_stock_basic
from quant_data.dimensions.market import write_trade_calendar
from quant_data.evaluation.factor import evaluate_factor
from quant_data.evaluation.stability import write_stability_reports
from quant_data.factors.baseline import compute_baseline_factors
from quant_data.factors.baseline import FACTOR_COLUMNS
from quant_data.factors.sentiment import compute_market_sentiment
from quant_data.factors.sentiment import join_market_sentiment
from quant_data.ingestion.akshare_a_share import ingest_stock_daily
from quant_data.ingestion.symbols import load_symbols
from quant_data.quality.rules import run_quality_checks
from quant_data.storage.clickhouse import get_client as get_clickhouse_client
from quant_data.storage.clickhouse import load_pipeline_outputs
from quant_data.storage.parquet import read_parquet, write_parquet


def _output_paths(output_dir: Path, factor_name: str) -> dict[str, Path]:
    return {
        "trade_calendar": output_dir / "dim" / "trade_calendar.parquet",
        "stock_basic": output_dir / "dim" / "stock_basic.parquet",
        "dwd": output_dir / "dwd" / "stock_daily.parquet",
        "quality": output_dir / "reports" / "data_quality_report.parquet",
        "factors": output_dir / "ads" / "factor_wide_daily.parquet",
        "market_sentiment": output_dir / "ads" / "market_sentiment_daily.parquet",
        "evaluation": output_dir / "ads" / f"factor_eval_{factor_name}.parquet",
        "backtest_daily": output_dir / "ads" / f"backtest_daily_{factor_name}.parquet",
        "backtest_metrics": output_dir / "ads" / f"backtest_metrics_{factor_name}.json",
    }


def run_clean(input_path: Path, output_dir: Path) -> Path:
    raw = read_parquet(input_path)
    cleaned = clean_daily_bars(raw)
    output_path = _output_paths(output_dir, "factor")["dwd"]
    return write_parquet(cleaned, output_path)


def run_ingest_akshare(
    symbols: str | None,
    symbols_file: Path | None,
    start_date: str,
    end_date: str,
    output_path: Path,
    report_path: Path,
    adjust: str,
    retries: int,
    retry_wait_seconds: float,
    request_interval_seconds: float,
    incremental: bool,
    run_log_path: Path,
) -> tuple[Path, Path]:
    symbol_list: list[str] = []
    if symbols:
        symbol_list.extend(symbol.strip() for symbol in symbols.split(",") if symbol.strip())
    if symbols_file:
        symbol_list.extend(load_symbols(symbols_file))
    if not symbol_list:
        raise ValueError("Provide at least one stock code with --symbols or --symbols-file")

    # CLI 层允许命令行和股票池文件组合使用，这里统一去重并保持输入顺序。
    deduplicated_symbols = list(dict.fromkeys(symbol_list))
    return ingest_stock_daily(
        symbols=deduplicated_symbols,
        start_date=start_date,
        end_date=end_date,
        output_path=output_path,
        report_path=report_path,
        adjust=adjust,
        retries=retries,
        retry_wait_seconds=retry_wait_seconds,
        request_interval_seconds=request_interval_seconds,
        incremental=incremental,
        run_log_path=run_log_path,
    )


def run_dimensions(output_dir: Path, start_date: str, end_date: str) -> tuple[Path, Path]:
    paths = _output_paths(output_dir, "factor")
    calendar_path = write_trade_calendar(start_date, end_date, paths["trade_calendar"])
    stock_basic_path = write_stock_basic(paths["stock_basic"])
    return calendar_path, stock_basic_path


def run_build_hs300_symbols(output_path: Path, filter_st: bool) -> Path:
    return write_hs300_symbol_pool(output_path, filter_st=filter_st)


def run_quality(output_dir: Path, min_rows_per_date: int, abnormal_return_threshold: float) -> Path:
    paths = _output_paths(output_dir, "factor")
    cleaned = read_parquet(paths["dwd"])
    report = run_quality_checks(
        cleaned,
        min_rows_per_date=min_rows_per_date,
        abnormal_return_threshold=abnormal_return_threshold,
    )
    return write_parquet(report, paths["quality"])


def run_factors(output_dir: Path) -> Path:
    paths = _output_paths(output_dir, "factor")
    cleaned = read_parquet(paths["dwd"])
    factors = compute_baseline_factors(cleaned)
    sentiment = compute_market_sentiment(cleaned)
    write_parquet(sentiment, paths["market_sentiment"])
    factors = join_market_sentiment(factors, sentiment)
    return write_parquet(factors, paths["factors"])


def run_evaluate(output_dir: Path, factor_name: str, horizon: int, groups: int) -> Path:
    paths = _output_paths(output_dir, factor_name)
    cleaned = read_parquet(paths["dwd"])
    factors = read_parquet(paths["factors"])
    report = evaluate_factor(factors, cleaned, factor_name, horizon=horizon, groups=groups)
    return write_parquet(report, paths["evaluation"])


def run_backtest(
    output_dir: Path,
    factor_name: str,
    top_quantile: float,
    rebalance_interval: int,
    transaction_cost: float,
    commission_rate: float,
    slippage_rate: float,
    stamp_tax_rate: float,
    sentiment_threshold: float | None = None,
    weak_sentiment_exposure: float = 0.5,
    normal_exposure: float = 1.0,
) -> tuple[Path, Path]:
    paths = _output_paths(output_dir, factor_name)
    cleaned = read_parquet(paths["dwd"])
    factors = read_parquet(paths["factors"])
    market_sentiment = None
    if sentiment_threshold is not None:
        market_sentiment = read_parquet(paths["market_sentiment"])
    daily_result, metrics = run_simple_backtest(
        factors,
        cleaned,
        factor_name,
        top_quantile=top_quantile,
        rebalance_interval=rebalance_interval,
        transaction_cost=transaction_cost,
        commission_rate=commission_rate,
        slippage_rate=slippage_rate,
        stamp_tax_rate=stamp_tax_rate,
        market_sentiment=market_sentiment,
        sentiment_threshold=sentiment_threshold,
        weak_sentiment_exposure=weak_sentiment_exposure,
        normal_exposure=normal_exposure,
    )
    daily_path = write_parquet(daily_result, paths["backtest_daily"])
    metrics_path = paths["backtest_metrics"]
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return daily_path, metrics_path


def _parse_factor_names(value: str | None) -> list[str]:
    if not value:
        return list(FACTOR_COLUMNS)
    return [factor.strip() for factor in value.split(",") if factor.strip()]


def run_factor_suite(
    output_dir: Path,
    factor_names: list[str],
    horizon: int,
    groups: int,
    top_quantile: float,
    rebalance_interval: int,
    transaction_cost: float,
    commission_rate: float,
    slippage_rate: float,
    stamp_tax_rate: float,
    sentiment_threshold: float | None = None,
    weak_sentiment_exposure: float = 0.5,
    normal_exposure: float = 1.0,
) -> list[tuple[Path, Path, Path]]:
    outputs = []
    for factor_name in factor_names:
        evaluation_path = run_evaluate(output_dir, factor_name, horizon, groups)
        daily_path, metrics_path = run_backtest(
            output_dir,
            factor_name,
            top_quantile,
            rebalance_interval,
            transaction_cost,
            commission_rate,
            slippage_rate,
            stamp_tax_rate,
            sentiment_threshold,
            weak_sentiment_exposure,
            normal_exposure,
        )
        outputs.append((evaluation_path, daily_path, metrics_path))
    return outputs


def run_stability(
    output_dir: Path,
    factor_names: list[str],
    rank_ic_window: int = 60,
    return_window: int = 120,
) -> tuple[Path, Path]:
    return write_stability_reports(output_dir, factor_names, rank_ic_window, return_window)


def run_load_clickhouse(
    output_dir: Path,
    factor_name: str,
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
) -> dict[str, int]:
    client = get_clickhouse_client(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
    )
    return load_pipeline_outputs(client, output_dir, factor_name=factor_name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run quant data engineering pipeline stages.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(stage: argparse.ArgumentParser) -> None:
        stage.add_argument("--output-dir", type=Path, default=Path("data"))

    clean = subparsers.add_parser("clean")
    clean.add_argument("--input", type=Path, required=True)
    add_common(clean)

    ingest_akshare = subparsers.add_parser("ingest-akshare")
    ingest_akshare.add_argument("--symbols")
    ingest_akshare.add_argument("--symbols-file", type=Path)
    ingest_akshare.add_argument("--start-date", required=True)
    ingest_akshare.add_argument("--end-date", required=True)
    ingest_akshare.add_argument("--adjust", default="qfq")
    ingest_akshare.add_argument("--output", type=Path, default=Path("data/ods/stock_daily.parquet"))
    ingest_akshare.add_argument("--report", type=Path, default=Path("data/reports/ingestion_report.parquet"))
    ingest_akshare.add_argument("--retries", type=int, default=2)
    ingest_akshare.add_argument("--retry-wait-seconds", type=float, default=1.0)
    ingest_akshare.add_argument("--request-interval-seconds", type=float, default=0.0)
    ingest_akshare.add_argument("--incremental", action="store_true")
    ingest_akshare.add_argument("--run-log", type=Path, default=Path("data/reports/ingestion_runs.parquet"))

    dimensions = subparsers.add_parser("dimensions")
    add_common(dimensions)
    dimensions.add_argument("--start-date", required=True)
    dimensions.add_argument("--end-date", required=True)

    hs300_symbols = subparsers.add_parser("build-hs300-symbols")
    hs300_symbols.add_argument("--output", type=Path, default=Path("configs/symbols.csv"))
    hs300_symbols.add_argument("--include-st", action="store_true")

    quality = subparsers.add_parser("quality")
    add_common(quality)
    quality.add_argument("--min-rows-per-date", type=int, default=1)
    quality.add_argument("--abnormal-return-threshold", type=float, default=0.2)

    factors = subparsers.add_parser("factors")
    add_common(factors)

    evaluate = subparsers.add_parser("evaluate")
    add_common(evaluate)
    evaluate.add_argument("--factor-name", default="momentum_20d")
    evaluate.add_argument("--horizon", type=int, default=5)
    evaluate.add_argument("--groups", type=int, default=5)

    backtest = subparsers.add_parser("backtest")
    add_common(backtest)
    backtest.add_argument("--factor-name", default="momentum_20d")
    backtest.add_argument("--top-quantile", type=float, default=0.1)
    backtest.add_argument("--rebalance-interval", type=int, default=20)
    backtest.add_argument("--transaction-cost", type=float, default=0.001)
    backtest.add_argument("--commission-rate", type=float, default=0.0003)
    backtest.add_argument("--slippage-rate", type=float, default=0.0005)
    backtest.add_argument("--stamp-tax-rate", type=float, default=0.0005)
    backtest.add_argument("--sentiment-threshold", type=float)
    backtest.add_argument("--weak-sentiment-exposure", type=float, default=0.5)
    backtest.add_argument("--normal-exposure", type=float, default=1.0)

    factor_suite = subparsers.add_parser("factor-suite")
    add_common(factor_suite)
    factor_suite.add_argument("--factor-names")
    factor_suite.add_argument("--horizon", type=int, default=5)
    factor_suite.add_argument("--groups", type=int, default=5)
    factor_suite.add_argument("--top-quantile", type=float, default=0.1)
    factor_suite.add_argument("--rebalance-interval", type=int, default=20)
    factor_suite.add_argument("--transaction-cost", type=float, default=0.001)
    factor_suite.add_argument("--commission-rate", type=float, default=0.0003)
    factor_suite.add_argument("--slippage-rate", type=float, default=0.0005)
    factor_suite.add_argument("--stamp-tax-rate", type=float, default=0.0005)
    factor_suite.add_argument("--sentiment-threshold", type=float)
    factor_suite.add_argument("--weak-sentiment-exposure", type=float, default=0.5)
    factor_suite.add_argument("--normal-exposure", type=float, default=1.0)

    stability = subparsers.add_parser("stability")
    add_common(stability)
    stability.add_argument("--factor-names")
    stability.add_argument("--rank-ic-window", type=int, default=60)
    stability.add_argument("--return-window", type=int, default=120)

    load_clickhouse = subparsers.add_parser("load-clickhouse")
    add_common(load_clickhouse)
    load_clickhouse.add_argument("--factor-name", default="momentum_20d")
    load_clickhouse.add_argument("--host", default="127.0.0.1")
    load_clickhouse.add_argument("--port", type=int, default=8123)
    load_clickhouse.add_argument("--username", default="default")
    load_clickhouse.add_argument("--password", required=True)
    load_clickhouse.add_argument("--database", default="quant_data")

    run_all = subparsers.add_parser("run-all")
    run_all.add_argument("--input", type=Path, required=True)
    add_common(run_all)
    run_all.add_argument("--factor-name", default="momentum_20d")
    run_all.add_argument("--horizon", type=int, default=5)
    run_all.add_argument("--groups", type=int, default=5)
    run_all.add_argument("--top-quantile", type=float, default=0.1)
    run_all.add_argument("--rebalance-interval", type=int, default=20)
    run_all.add_argument("--transaction-cost", type=float, default=0.001)
    run_all.add_argument("--commission-rate", type=float, default=0.0003)
    run_all.add_argument("--slippage-rate", type=float, default=0.0005)
    run_all.add_argument("--stamp-tax-rate", type=float, default=0.0005)
    run_all.add_argument("--sentiment-threshold", type=float)
    run_all.add_argument("--weak-sentiment-exposure", type=float, default=0.5)
    run_all.add_argument("--normal-exposure", type=float, default=1.0)
    run_all.add_argument("--min-rows-per-date", type=int, default=1)
    run_all.add_argument("--abnormal-return-threshold", type=float, default=0.2)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # CLI 只负责串联各阶段；具体业务逻辑仍然放在 cleaning/quality/factors 等模块里。
    if args.command == "clean":
        run_clean(args.input, args.output_dir)
    elif args.command == "ingest-akshare":
        run_ingest_akshare(
            args.symbols,
            args.symbols_file,
            args.start_date,
            args.end_date,
            args.output,
            args.report,
            args.adjust,
            args.retries,
            args.retry_wait_seconds,
            args.request_interval_seconds,
            args.incremental,
            args.run_log,
        )
    elif args.command == "dimensions":
        run_dimensions(args.output_dir, args.start_date, args.end_date)
    elif args.command == "build-hs300-symbols":
        run_build_hs300_symbols(args.output, filter_st=not args.include_st)
    elif args.command == "quality":
        run_quality(args.output_dir, args.min_rows_per_date, args.abnormal_return_threshold)
    elif args.command == "factors":
        run_factors(args.output_dir)
    elif args.command == "evaluate":
        run_evaluate(args.output_dir, args.factor_name, args.horizon, args.groups)
    elif args.command == "backtest":
        run_backtest(
            args.output_dir,
            args.factor_name,
            args.top_quantile,
            args.rebalance_interval,
            args.transaction_cost,
            args.commission_rate,
            args.slippage_rate,
            args.stamp_tax_rate,
            args.sentiment_threshold,
            args.weak_sentiment_exposure,
            args.normal_exposure,
        )
    elif args.command == "factor-suite":
        run_factor_suite(
            args.output_dir,
            _parse_factor_names(args.factor_names),
            args.horizon,
            args.groups,
            args.top_quantile,
            args.rebalance_interval,
            args.transaction_cost,
            args.commission_rate,
            args.slippage_rate,
            args.stamp_tax_rate,
            args.sentiment_threshold,
            args.weak_sentiment_exposure,
            args.normal_exposure,
        )
        run_stability(args.output_dir, _parse_factor_names(args.factor_names))
    elif args.command == "stability":
        run_stability(args.output_dir, _parse_factor_names(args.factor_names), args.rank_ic_window, args.return_window)
    elif args.command == "load-clickhouse":
        run_load_clickhouse(
            args.output_dir,
            args.factor_name,
            args.host,
            args.port,
            args.username,
            args.password,
            args.database,
        )
    elif args.command == "run-all":
        run_clean(args.input, args.output_dir)
        run_quality(args.output_dir, args.min_rows_per_date, args.abnormal_return_threshold)
        run_factors(args.output_dir)
        run_evaluate(args.output_dir, args.factor_name, args.horizon, args.groups)
        run_backtest(
            args.output_dir,
            args.factor_name,
            args.top_quantile,
            args.rebalance_interval,
            args.transaction_cost,
            args.commission_rate,
            args.slippage_rate,
            args.stamp_tax_rate,
            args.sentiment_threshold,
            args.weak_sentiment_exposure,
            args.normal_exposure,
        )
        run_stability(args.output_dir, [args.factor_name])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
