import argparse
import json
from pathlib import Path

from quant_data.backtest.simple import run_simple_backtest
from quant_data.cleaning.daily import clean_daily_bars
from quant_data.evaluation.factor import evaluate_factor
from quant_data.factors.baseline import compute_baseline_factors
from quant_data.quality.rules import run_quality_checks
from quant_data.storage.parquet import read_parquet, write_parquet


def _output_paths(output_dir: Path, factor_name: str) -> dict[str, Path]:
    return {
        "dwd": output_dir / "dwd" / "stock_daily.parquet",
        "quality": output_dir / "reports" / "data_quality_report.parquet",
        "factors": output_dir / "ads" / "factor_wide_daily.parquet",
        "evaluation": output_dir / "ads" / f"factor_eval_{factor_name}.parquet",
        "backtest_daily": output_dir / "ads" / f"backtest_daily_{factor_name}.parquet",
        "backtest_metrics": output_dir / "ads" / f"backtest_metrics_{factor_name}.json",
    }


def run_clean(input_path: Path, output_dir: Path) -> Path:
    raw = read_parquet(input_path)
    cleaned = clean_daily_bars(raw)
    output_path = _output_paths(output_dir, "factor")["dwd"]
    return write_parquet(cleaned, output_path)


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
) -> tuple[Path, Path]:
    paths = _output_paths(output_dir, factor_name)
    cleaned = read_parquet(paths["dwd"])
    factors = read_parquet(paths["factors"])
    daily_result, metrics = run_simple_backtest(
        factors,
        cleaned,
        factor_name,
        top_quantile=top_quantile,
        rebalance_interval=rebalance_interval,
        transaction_cost=transaction_cost,
    )
    daily_path = write_parquet(daily_result, paths["backtest_daily"])
    metrics_path = paths["backtest_metrics"]
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return daily_path, metrics_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run quant data engineering pipeline stages.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(stage: argparse.ArgumentParser) -> None:
        stage.add_argument("--output-dir", type=Path, default=Path("data"))

    clean = subparsers.add_parser("clean")
    clean.add_argument("--input", type=Path, required=True)
    add_common(clean)

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

    run_all = subparsers.add_parser("run-all")
    run_all.add_argument("--input", type=Path, required=True)
    add_common(run_all)
    run_all.add_argument("--factor-name", default="momentum_20d")
    run_all.add_argument("--horizon", type=int, default=5)
    run_all.add_argument("--groups", type=int, default=5)
    run_all.add_argument("--top-quantile", type=float, default=0.1)
    run_all.add_argument("--rebalance-interval", type=int, default=20)
    run_all.add_argument("--transaction-cost", type=float, default=0.001)
    run_all.add_argument("--min-rows-per-date", type=int, default=1)
    run_all.add_argument("--abnormal-return-threshold", type=float, default=0.2)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # CLI 只负责串联各阶段；具体业务逻辑仍然放在 cleaning/quality/factors 等模块里。
    if args.command == "clean":
        run_clean(args.input, args.output_dir)
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
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
