param(
    [ValidatePattern('^\d{8}$')]
    [string]$StartDate,

    [ValidatePattern('^\d{8}$')]
    [string]$EndDate,

    [string]$SymbolsFile = "configs/symbols.csv",
    [bool]$BuildHs300Symbols = $false,
    [string]$FactorName = "momentum_20d_zscore",
    [string]$FactorNames = "momentum_20d,reversal_5d,volatility_20d,volume_ratio_5d,ma_bias_20d,momentum_20d_zscore,reversal_5d_zscore,volatility_20d_zscore,volume_ratio_5d_zscore,ma_bias_20d_zscore",
    [int]$Groups = 5,
    [int]$MinRowsPerDate = 20,
    [double]$AbnormalReturnThreshold = 0.25,
    [double]$TransactionCost = 0.001,
    [double]$CommissionRate = 0.0003,
    [double]$SlippageRate = 0.0005,
    [double]$StampTaxRate = 0.0005,
    [ValidateSet("top", "bottom")]
    [string]$FactorDirection = "top",
    [double]$TopQuantile = 0.1,
    [int]$RebalanceInterval = 20,
    [Nullable[double]]$EntryQuantile = $null,
    [Nullable[double]]$ExitQuantile = $null,
    [Nullable[double]]$SentimentThreshold = $null,
    [ValidateSet("step", "smooth")]
    [string]$SentimentMode = "step",
    [double]$SentimentSmoothAlpha = 0.2,
    [double]$MinExposure = 0.3,
    [double]$MaxExposure = 1.0,
    [double]$BaseExposure = 0.6,
    [double]$SentimentScale = 0.2,
    [double]$WeakSentimentExposure = 0.5,
    [double]$NormalExposure = 1.0,
    [int]$Retries = 3,
    [double]$RetryWaitSeconds = 2,
    [double]$RequestIntervalSeconds = 0.5,
    [bool]$Incremental = $true,
    [bool]$LoadClickHouse = $true,
    [string]$EnvFile = ".env",
    [string]$ClickHouseHost = "127.0.0.1",
    [int]$ClickHousePort = 8123,
    [string]$ClickHouseUser = "default",
    [string]$ClickHousePassword = $env:CLICKHOUSE_PASSWORD,
    [string]$ClickHouseDatabase = "quant_data"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$EnvPath = Join-Path $ProjectRoot $EnvFile
if (-not $ClickHousePassword -and (Test-Path $EnvPath)) {
    Get-Content $EnvPath | ForEach-Object {
        $Line = $_.Trim()
        if (-not $Line -or $Line.StartsWith("#") -or -not $Line.Contains("=")) {
            return
        }
        $Key, $Value = $Line.Split("=", 2)
        if ($Key.Trim() -eq "CLICKHOUSE_PASSWORD") {
            $ClickHousePassword = $Value.Trim().Trim('"').Trim("'")
        }
    }
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found: $Python"
}

if (-not $StartDate) {
    throw "StartDate is required, for example: -StartDate 20240101"
}
if (-not $EndDate) {
    throw "EndDate is required, for example: -EndDate 20241231"
}
if ($StartDate -gt $EndDate) {
    throw "StartDate must be earlier than or equal to EndDate."
}

$OdsPath = "data/ods/stock_daily.parquet"
$IngestionReportPath = "data/reports/ingestion_report.parquet"
$IngestionRunLogPath = "data/reports/ingestion_runs.parquet"

if ($BuildHs300Symbols) {
    Write-Host "Step 1/6 Build CSI 300 symbol pool"
    & $Python -m quant_data.cli build-hs300-symbols --output $SymbolsFile
} else {
    Write-Host "Step 1/6 Use existing symbol pool: $SymbolsFile"
}

Write-Host "Step 2/6 Build dimension tables"
& $Python -m quant_data.cli dimensions `
    --start-date $StartDate `
    --end-date $EndDate `
    --output-dir data

Write-Host "Step 3/6 Ingest CSI 300 index benchmark"
& $Python -m quant_data.cli ingest-hs300-index `
    --start-date $StartDate `
    --end-date $EndDate `
    --output-dir data

Write-Host "Step 4/6 Ingest A-share daily data"
$IngestArgs = @(
    "-m", "quant_data.cli", "ingest-akshare",
    "--symbols-file", $SymbolsFile,
    "--start-date", $StartDate,
    "--end-date", $EndDate,
    "--adjust", "qfq",
    "--output", $OdsPath,
    "--report", $IngestionReportPath,
    "--retries", "$Retries",
    "--retry-wait-seconds", "$RetryWaitSeconds",
    "--request-interval-seconds", "$RequestIntervalSeconds",
    "--run-log", $IngestionRunLogPath
)
if ($Incremental) {
    $IngestArgs += "--incremental"
}
& $Python @IngestArgs

Write-Host "Step 5/6 Run local data pipeline"
$RunAllArgs = @(
    "-m", "quant_data.cli", "run-all",
    "--input", $OdsPath,
    "--output-dir", "data",
    "--factor-name", $FactorName,
    "--groups", "$Groups",
    "--min-rows-per-date", "$MinRowsPerDate",
    "--abnormal-return-threshold", "$AbnormalReturnThreshold",
    "--transaction-cost", "$TransactionCost",
    "--commission-rate", "$CommissionRate",
    "--slippage-rate", "$SlippageRate",
    "--stamp-tax-rate", "$StampTaxRate",
    "--factor-direction", "$FactorDirection",
    "--top-quantile", "$TopQuantile",
    "--rebalance-interval", "$RebalanceInterval",
    "--sentiment-mode", "$SentimentMode",
    "--sentiment-smooth-alpha", "$SentimentSmoothAlpha",
    "--min-exposure", "$MinExposure",
    "--max-exposure", "$MaxExposure",
    "--base-exposure", "$BaseExposure",
    "--sentiment-scale", "$SentimentScale"
)
if ($null -ne $EntryQuantile) {
    $RunAllArgs += @("--entry-quantile", "$EntryQuantile")
}
if ($null -ne $ExitQuantile) {
    $RunAllArgs += @("--exit-quantile", "$ExitQuantile")
}
if ($null -ne $SentimentThreshold) {
    $RunAllArgs += @(
        "--sentiment-threshold", "$SentimentThreshold",
        "--weak-sentiment-exposure", "$WeakSentimentExposure",
        "--normal-exposure", "$NormalExposure"
    )
}
& $Python @RunAllArgs

$FactorSuiteArgs = @(
    "-m", "quant_data.cli", "factor-suite",
    "--output-dir", "data",
    "--factor-names", $FactorNames,
    "--groups", "$Groups",
    "--transaction-cost", "$TransactionCost",
    "--commission-rate", "$CommissionRate",
    "--slippage-rate", "$SlippageRate",
    "--stamp-tax-rate", "$StampTaxRate",
    "--factor-direction", "$FactorDirection",
    "--top-quantile", "$TopQuantile",
    "--rebalance-interval", "$RebalanceInterval",
    "--sentiment-mode", "$SentimentMode",
    "--sentiment-smooth-alpha", "$SentimentSmoothAlpha",
    "--min-exposure", "$MinExposure",
    "--max-exposure", "$MaxExposure",
    "--base-exposure", "$BaseExposure",
    "--sentiment-scale", "$SentimentScale"
)
if ($null -ne $EntryQuantile) {
    $FactorSuiteArgs += @("--entry-quantile", "$EntryQuantile")
}
if ($null -ne $ExitQuantile) {
    $FactorSuiteArgs += @("--exit-quantile", "$ExitQuantile")
}
if ($null -ne $SentimentThreshold) {
    $FactorSuiteArgs += @(
        "--sentiment-threshold", "$SentimentThreshold",
        "--weak-sentiment-exposure", "$WeakSentimentExposure",
        "--normal-exposure", "$NormalExposure"
    )
}
& $Python @FactorSuiteArgs

if ($LoadClickHouse -and $ClickHousePassword) {
    Write-Host "Step 6/6 Load results into ClickHouse"
    & $Python -m quant_data.cli load-clickhouse `
        --output-dir data `
        --factor-name $FactorName `
        --host $ClickHouseHost `
        --port $ClickHousePort `
        --username $ClickHouseUser `
        --password $ClickHousePassword `
        --database $ClickHouseDatabase
} elseif ($LoadClickHouse) {
    Write-Warning "Step 6/6 skipped ClickHouse load because ClickHousePassword or CLICKHOUSE_PASSWORD is not set."
} else {
    Write-Host "Step 6/6 Skip ClickHouse load"
}

Write-Host "Print run summary"
$env:PIPELINE_FACTOR_NAME = $FactorName
$SummaryCode = @'
import json
import os
from pathlib import Path

import pandas as pd

def print_frame_status(name: str, path: str, symbol_col: str | None = None) -> None:
    file_path = Path(path)
    if not file_path.exists():
        print(f"{name}: missing")
        return
    frame = pd.read_parquet(file_path)
    parts = [f"{name}: rows={len(frame)}"]
    if symbol_col and symbol_col in frame.columns:
        parts.append(f"symbols={frame[symbol_col].nunique()}")
    print(", ".join(parts))

print_frame_status("ingestion_report", "data/reports/ingestion_report.parquet")
if Path("data/reports/ingestion_report.parquet").exists():
    report = pd.read_parquet("data/reports/ingestion_report.parquet")
    print("ingestion_status_counts:", report["status"].value_counts().to_dict())

print_frame_status("ods_stock_daily", "data/ods/stock_daily.parquet", "symbol")
print_frame_status("dim_trade_calendar", "data/dim/trade_calendar.parquet")
print_frame_status("dim_stock_basic", "data/dim/stock_basic.parquet", "symbol")
print_frame_status("dim_hs300_index", "data/dim/hs300_index.parquet")
print_frame_status("dwd_stock_daily", "data/dwd/stock_daily.parquet", "symbol")
print_frame_status("factor_wide_daily", "data/ads/factor_wide_daily.parquet", "symbol")
factor_name = os.environ.get("PIPELINE_FACTOR_NAME", "momentum_20d")
print_frame_status("factor_eval", f"data/ads/factor_eval_{factor_name}.parquet")
print_frame_status("backtest_daily", f"data/ads/backtest_daily_{factor_name}.parquet")
print_frame_status("factor_yearly_summary", "data/ads/factor_yearly_summary.parquet")
print_frame_status("factor_rolling_summary", "data/ads/factor_rolling_summary.parquet")
print_frame_status("parameter_sensitivity", "data/ads/parameter_sensitivity.parquet")
print_frame_status("cost_sensitivity", "data/ads/cost_sensitivity.parquet")

metrics_path = Path(f"data/ads/backtest_metrics_{factor_name}.json")
if metrics_path.exists():
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    print("backtest_metrics:", metrics)

runs_path = Path("data/reports/ingestion_runs.parquet")
if runs_path.exists():
    runs = pd.read_parquet(runs_path)
    print("last_ingestion_run:")
    print(runs.tail(1).to_string(index=False))
'@
& $Python -c $SummaryCode
