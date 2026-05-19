# 量化数据工程项目

这是一个本地可运行的 A 股量化数据工程项目，围绕行情采集、数据分层、质量校验、因子计算、因子评估、策略回测、ClickHouse 入库和 Streamlit 可视化看板，构建一条完整的量化数据处理链路。

`README.md` 更偏对外展示，保持简洁；本文档是中文详细使用说明，重点解释每个模块怎么运行、输入输出是什么、各个 CLI 参数有什么作用。

## 项目亮点

- **完整数据链路**：覆盖 ODS 原始行情、DWD 清洗日线、DIM 维表、ADS 因子宽表、评估结果、回测结果和诊断分析结果。
- **真实数据接入**：支持通过 AkShare 采集 A 股日线行情，并支持股票池文件、重试、请求间隔、增量采集和采集日志。
- **质量可观测**：内置主键唯一性、必填字段、价格合法性、成交量、日期完整性和异常收益等质量规则。
- **因子研究闭环**：实现基础量价因子、市场情绪因子、IC/RankIC、分组收益、年度表现、滚动稳定性分析。
- **策略诊断能力**：支持因子方向验证、持仓缓冲区、参数敏感性分析、成本敏感性分析和平滑情绪择时。
- **回测约束更贴近市场**：支持防未来函数、下一交易日执行、调仓周期、交易成本、佣金、滑点、印花税、停牌和涨跌停交易约束。
- **工程化输出**：提供 CLI 一键流水线、ClickHouse 写入、数据库查询接口、Streamlit 看板和 pytest 自动化测试。

## 数据链路

项目构建的数据工程流水线：

```text
AkShare / fixture 数据
-> ODS 原始行情数据
-> DWD 清洗后日线数据
-> DIM 交易日历 / 股票基础信息 / 沪深300指数
-> 数据质量报告
-> ADS 因子宽表 + 市场情绪表
-> 因子有效性评估
-> 策略回测
-> 年度表现 / 滚动稳定性
-> 参数敏感性 / 成本敏感性
-> ClickHouse 分析表
-> Streamlit 看板
```

## 技术栈

```text
Python
pandas / numpy
PyArrow / Parquet
pytest
argparse CLI
AkShare
ClickHouse
Streamlit
```

## 快速运行

日常更新和完整重跑推荐直接执行一键脚本：

```powershell
.\scripts\run_daily_pipeline.ps1 `
  -StartDate 20240101 `
  -EndDate 20241231
```

这个命令会按 `configs/symbols.csv` 股票池执行增量采集，然后自动完成维表构建、指数采集、清洗、质量检查、因子计算、因子评估、回测、稳定性分析、参数敏感性分析、成本敏感性分析，并在配置了 ClickHouse 密码时自动写入 ClickHouse。

启动看板：

```powershell
.\.venv\Scripts\streamlit.exe run src\quant_data\dashboard\app.py
```

默认读取 `data` 目录下的 Parquet 和 JSON 结果，可以在页面左侧修改数据目录。

## 当前功能

### 1. 日线数据采集

模块：`src/quant_data/ingestion/akshare_a_share.py`

CLI：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli ingest-akshare `
  --symbols-file configs/symbols.csv `
  --start-date 20240101 `
  --end-date 20241231 `
  --adjust qfq `
  --output data/ods/stock_daily.parquet `
  --report data/reports/ingestion_report.parquet `
  --retries 3 `
  --retry-wait-seconds 2 `
  --request-interval-seconds 0.5 `
  --incremental `
  --run-log data/reports/ingestion_runs.parquet
```

功能：

- 支持直接传入 `--symbols 000001,600000,600519`。
- 支持通过 `--symbols-file configs/symbols.csv` 读取股票池。
- 支持 `--incremental` 增量采集，只补采本地已有最大日期之后的数据。
- 支持 `--retries` 和 `--retry-wait-seconds`，降低外部接口短暂失败影响。
- 支持 `--request-interval-seconds`，避免请求过快。
- 输出单只股票采集报告和整次运行日志。

采集状态：

```text
SUCCESS: 成功采集到非空行情数据
FAILED : 接口调用失败或字段不符合预期
EMPTY  : 接口正常返回，但没有行情行
SKIPPED: 增量采集时本地数据已覆盖目标日期范围，本次跳过
```

主要输出：

```text
data/ods/stock_daily.parquet
data/reports/ingestion_report.parquet
data/reports/ingestion_runs.parquet
```

### 2. 股票池和维表

模块：

```text
src/quant_data/dimensions/market.py
src/quant_data/ingestion/index.py
```

生成沪深 300 股票池：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli build-hs300-symbols `
  --output configs/symbols.csv
```

一键脚本中自动生成：

```powershell
.\scripts\run_daily_pipeline.ps1 `
  -StartDate 20200101 `
  -EndDate 20241231 `
  -BuildHs300Symbols $true
```

维表生成：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli dimensions `
  --start-date 20200101 `
  --end-date 20241231 `
  --output-dir data
```

沪深 300 指数基准采集：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli ingest-hs300-index `
  --start-date 20200101 `
  --end-date 20241231 `
  --output-dir data
```

主要输出：

```text
configs/symbols.csv
data/dim/trade_calendar.parquet
data/dim/stock_basic.parquet
data/dim/hs300_index.parquet
```

说明：

- `stock_basic` 会包含股票代码、简称、交易所、是否 ST。
- 默认构建沪深 300 股票池时过滤 ST 股票。
- `hs300_index` 用于回测中的沪深 300 指数基准。

### 3. 日线数据清洗

模块：`src/quant_data/cleaning/daily.py`

CLI：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli clean `
  --input data/ods/stock_daily.parquet `
  --output-dir data
```

功能：

- 标准化交易日期。
- 标准化 A 股股票代码后缀，例如 `000001` 转成 `000001.SZ`。
- 转换 OHLCV 数值字段。
- 去重。
- 按股票计算 `return_1d`。
- 生成近似停牌标识 `is_suspended`。
- 生成近似涨停 / 跌停标识 `is_limit_up`、`is_limit_down`。

输出：

```text
data/dwd/stock_daily.parquet
```

### 4. 数据质量检查

模块：`src/quant_data/quality/rules.py`

CLI：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli quality `
  --output-dir data `
  --min-rows-per-date 20 `
  --abnormal-return-threshold 0.25
```

检查规则：

- 主键唯一性：`trade_date + symbol` 是否唯一。
- 必填字段非空：`open/high/low/close/volume`。
- 价格合法性：价格非负、`close > 0`、`high >= low`。
- 成交量合法性：`volume >= 0`。
- 日期完整性：每个交易日至少有指定股票数量。
- 异常收益：`abs(return_1d)` 是否超过阈值。

输出字段：

```text
rule_name
status
failed_count
failed_sample
```

输出：

```text
data/reports/data_quality_report.parquet
```

### 5. 基础因子计算

模块：`src/quant_data/factors/baseline.py`

CLI：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli factors `
  --output-dir data
```

已实现基础因子：

```text
momentum_20d      20 日动量
reversal_5d      5 日反转
volatility_20d   20 日波动率
volume_ratio_5d  5 日量比
ma_bias_20d      20 日均线偏离
```

同时会生成去极值和标准化版本：

```text
<factor>_winsorized
<factor>_zscore
```

处理逻辑：

- 滚动因子按 `symbol` 分组计算，避免不同股票数据串线。
- 去极值按交易日截面进行 1% / 99% 分位截断。
- z-score 按交易日截面标准化，统一不同因子量纲。

输出：

```text
data/ads/factor_wide_daily.parquet
```

### 6. 行情衍生市场情绪因子

模块：`src/quant_data/factors/sentiment.py`

`factors` 命令会同步生成市场情绪表。

已实现：

- 市场宽度：
  - `market_up_ratio`
  - `market_down_ratio`
  - `market_strong_ratio`
  - `market_weak_ratio`
- 成交活跃度：
  - `market_amount`
  - `market_volume`
  - `market_amount_ratio_20d`
  - `market_volume_ratio_20d`
- 赚钱效应：
  - `market_return_mean`
  - `market_return_median`
  - `market_return_positive_mean`
  - `market_return_negative_mean`
  - `profit_effect`
- 综合市场情绪：
  - `market_sentiment_score`

输出：

```text
data/ads/market_sentiment_daily.parquet
```

核心情绪字段也会按 `trade_date` 合并回：

```text
data/ads/factor_wide_daily.parquet
```

### 7. 因子评估

模块：`src/quant_data/evaluation/factor.py`

CLI：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli evaluate `
  --output-dir data `
  --factor-name momentum_20d_zscore `
  --horizon 5 `
  --groups 5
```

评估指标：

- 未来 N 日收益。
- IC：因子值与未来收益的 Pearson 截面相关。
- RankIC：因子排名与未来收益排名的 Spearman 截面相关。
- Top 组收益。
- Bottom 组收益。
- Top-Bottom 多空收益。

输出字段：

```text
trade_date
factor_name
ic
rank_ic
top_group_return
bottom_group_return
long_short_return
```

输出：

```text
data/ads/factor_eval_<factor_name>.parquet
```

### 8. 简单回测

模块：`src/quant_data/backtest/simple.py`

CLI：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli backtest `
  --output-dir data `
  --factor-name momentum_20d_zscore `
  --top-quantile 0.1 `
  --rebalance-interval 20
```

基础规则：

- 调仓日使用信号日因子。
- 信号只在下一交易日执行，避免未来函数。
- 默认按因子值最高的 `top_quantile` 股票等权持有。
- 支持股票池等权基准和沪深 300 指数基准。
- 支持成本前净值和成本后净值。
- 支持停牌、涨停不可买入、跌停不可卖出的近似交易约束。

成本参数：

```text
--transaction-cost
--commission-rate
--slippage-rate
--stamp-tax-rate
```

主要输出：

```text
data/ads/backtest_daily_<factor_name>.parquet
data/ads/backtest_metrics_<factor_name>.json
```

主要指标：

```text
total_return
gross_total_return
cost_drag
cost_to_return
annualized_return
equal_weight_total_return
hs300_total_return
hs300_excess_return
max_drawdown
sharpe
turnover
total_cost
average_exposure
```

## 策略诊断模块

这一部分是当前项目继续深化的重点。目标不是强行提高收益，而是让回测结果更可诊断：因子方向是否正确、换手是否过高、成本是否侵蚀收益、参数是否过拟合、情绪择时是否过于突兀。

### 1. 因子方向验证

不是所有因子都是“值越大越好”。

例如：

- `momentum_20d`：通常高值可能更强。
- `reversal_5d`：方向需要验证。
- `volatility_20d`：低波动可能更稳。
- `ma_bias_20d`：高偏离可能存在回落风险。
- `volume_ratio_5d`：高成交活跃不一定代表未来收益更高。

参数：

```text
--factor-direction top
--factor-direction bottom
```

高因子值组合：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli backtest `
  --output-dir data `
  --factor-name volatility_20d `
  --factor-direction top
```

低因子值组合：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli backtest `
  --output-dir data `
  --factor-name volatility_20d `
  --factor-direction bottom
```

输出 JSON 会记录：

```json
{
  "factor_direction": "top"
}
```

### 2. 持仓缓冲区

目的：降低不必要换手，减少交易成本侵蚀。

参数：

```text
--entry-quantile
--exit-quantile
```

无缓冲：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli backtest `
  --output-dir data `
  --factor-name ma_bias_20d `
  --top-quantile 0.1 `
  --rebalance-interval 20
```

有缓冲：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli backtest `
  --output-dir data `
  --factor-name ma_bias_20d `
  --entry-quantile 0.1 `
  --exit-quantile 0.3 `
  --rebalance-interval 20
```

逻辑：

- `entry_quantile = 0.1`：新股票必须进入前 10% 才允许买入。
- `exit_quantile = 0.3`：已有持仓只要仍在前 30% 内就继续持有。
- 如果 `factor_direction = bottom`，则表示最低 10%、最低 30%。
- 最终持仓数量尽量保持与 `top_quantile` 对应的目标数量一致。

新增指标：

```text
entry_quantile
exit_quantile
average_holding_count
rebalance_count
average_turnover_per_rebalance
```

### 3. 情绪择时仓位

支持两种模式：

```text
step
smooth
```

#### step 模式

step 是阈值硬切换：

```text
if market_sentiment_score < threshold:
    target_exposure = weak_sentiment_exposure
else:
    target_exposure = normal_exposure
```

示例：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli backtest `
  --output-dir data `
  --factor-name momentum_20d_zscore `
  --sentiment-threshold 0 `
  --weak-sentiment-exposure 0.3 `
  --normal-exposure 1.0
```

#### smooth 模式

smooth 是连续仓位 + 指数平滑：

```text
raw_target_exposure = base_exposure + sentiment_scale * market_sentiment_score
raw_target_exposure = clip(raw_target_exposure, min_exposure, max_exposure)

target_exposure_today =
    alpha * raw_target_exposure_today
  + (1 - alpha) * target_exposure_yesterday
```

示例：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli backtest `
  --output-dir data `
  --factor-name momentum_20d_zscore `
  --factor-direction top `
  --entry-quantile 0.1 `
  --exit-quantile 0.3 `
  --rebalance-interval 20 `
  --sentiment-mode smooth `
  --min-exposure 0.3 `
  --max-exposure 1.0 `
  --base-exposure 0.6 `
  --sentiment-scale 0.2 `
  --sentiment-smooth-alpha 0.2
```

回测日表新增字段：

```text
market_sentiment_score
raw_target_exposure
target_exposure
sentiment_mode
```

回测指标新增字段：

```text
sentiment_mode
min_exposure
max_exposure
base_exposure
sentiment_scale
sentiment_smooth_alpha
average_exposure
exposure_turnover
```

### 4. 参数敏感性分析

模块：`src/quant_data/evaluation/sensitivity.py`

CLI：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli sensitivity `
  --output-dir data
```

默认测试：

```text
factor_names:
  momentum_20d,reversal_5d,volatility_20d,volume_ratio_5d,ma_bias_20d

factor_directions:
  top,bottom

top_quantiles:
  0.1,0.2,0.3

rebalance_intervals:
  10,20,40,60
```

自定义示例：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli sensitivity `
  --output-dir data `
  --factor-names momentum_20d_zscore,ma_bias_20d `
  --factor-directions top,bottom `
  --top-quantiles 0.1,0.2 `
  --rebalance-intervals 20,40
```

输出：

```text
data/ads/parameter_sensitivity.parquet
```

核心字段：

```text
factor_name
factor_direction
top_quantile
rebalance_interval
total_return
benchmark_total_return
index_total_return
excess_return
index_excess_return
annualized_return
max_drawdown
sharpe
turnover
total_cost
cost_drag
cost_to_return
average_exposure
```

排序逻辑：

```text
sharpe desc
excess_return desc
max_drawdown desc
turnover asc
```

### 5. 成本敏感性分析

模块：`src/quant_data/evaluation/cost.py`

CLI：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli cost-sensitivity `
  --output-dir data `
  --factor-name momentum_20d_zscore `
  --factor-direction top `
  --top-quantile 0.1 `
  --rebalance-interval 20
```

输出：

```text
data/ads/cost_sensitivity.parquet
```

成本场景：

```text
no_cost:
  commission = 0
  stamp_tax = 0
  slippage = 0

low_cost:
  commission = 0.0001
  stamp_tax = 0.0005
  slippage = 0.0002

default_cost:
  commission = 0.0003
  stamp_tax = 0.0005
  slippage = 0.0005

high_cost:
  commission = 0.0005
  stamp_tax = 0.001
  slippage = 0.001
```

核心字段：

```text
factor_name
factor_direction
cost_scenario
commission
stamp_tax
slippage
total_return
before_cost_total_return
cost_drag
cost_to_return
max_drawdown
sharpe
turnover
```

解读方式：

- `no_cost` 到 `high_cost` 的 `total_return` 通常应逐步下降。
- `cost_drag` 越大，说明交易成本侵蚀越明显。
- 如果加成本后 Sharpe 明显下降，说明策略对成本假设敏感。
- 如果 turnover 很高，同时 cost_drag 很大，说明需要考虑更长调仓周期或持仓缓冲区。

## Streamlit 展示看板

模块：`src/quant_data/dashboard/app.py`

启动：

```powershell
.\.venv\Scripts\streamlit.exe run src\quant_data\dashboard\app.py
```

看板包含 3 个核心页面。

### 1. 数据链路概览

回答的问题：

```text
当前数据链路是否完整、可靠、可追踪？
```

展示内容：

- ODS 行数。
- DWD 行数。
- ADS 因子宽表行数。
- 股票数量。
- 日期范围。
- 最新交易日。
- 采集成功 / 跳过 / 异常数量。
- 链路正常率。
- 质量规则通过情况。
- 采集异常 / 空返回列表。
- 质量异常规则。

### 2. 因子有效性评估

回答的问题：

```text
这个因子有没有一定选股解释力？
```

展示内容：

- 多因子对比表。
- 因子选择框。
- IC 均值。
- RankIC 均值。
- 正 IC 占比。
- ICIR。
- 自动文字解读。
- IC / RankIC 曲线。
- Top / Bottom / Long-Short 平均收益。
- 年度表现。
- 滚动稳定性。

多因子对比表包含：

```text
factor_name
factor_direction
top_quantile
rebalance_interval
ic_mean
rank_ic_mean
positive_ic_ratio
icir
total_return
excess_return
max_drawdown
sharpe
turnover
total_cost
cost_drag
cost_to_return
```

### 3. 策略回测表现

回答的问题：

```text
使用这个因子构建策略后，收益和风险表现如何？
```

展示内容：

- 策略累计收益。
- 股票池等权基准收益。
- 沪深 300 指数收益。
- 指数超额收益。
- 最大回撤。
- Sharpe。
- 换手。
- 平均仓位。
- 成本前累计收益。
- 成本侵蚀。
- 成本 / 收益。
- 策略净值 vs 基准净值。
- 回撤曲线。
- 情绪择时仓位曲线。
- 参数敏感性 Top 20。
- 成本敏感性表和图。

## CLI 串联流程

CLI 的作用是把各个模块串成可执行的数据流水线。每个命令读取上一阶段的 Parquet 输出，再写入下一阶段结果。

日常运行推荐使用一键脚本：

```powershell
.\scripts\run_daily_pipeline.ps1 `
  -StartDate 20240101 `
  -EndDate 20241231
```

脚本会执行：

```text
1. 使用现有股票池，或自动构建沪深 300 股票池
2. 生成交易日历和股票基础信息维表
3. 采集沪深 300 指数基准
4. 增量采集 A 股日线数据
5. 清洗 DWD 日线
6. 运行数据质量检查
7. 计算基础因子和市场情绪因子
8. 评估指定因子
9. 回测指定因子
10. 生成年度表现和滚动稳定性
11. 生成参数敏感性分析
12. 生成成本敏感性分析
13. 如果配置了 ClickHouse 密码，自动写入 ClickHouse
```

带策略诊断参数的一键脚本：

```powershell
.\scripts\run_daily_pipeline.ps1 `
  -StartDate 20200101 `
  -EndDate 20241231 `
  -FactorName momentum_20d_zscore `
  -FactorDirection top `
  -TopQuantile 0.1 `
  -EntryQuantile 0.1 `
  -ExitQuantile 0.3 `
  -RebalanceInterval 20 `
  -SentimentMode smooth `
  -MinExposure 0.3 `
  -MaxExposure 1.0 `
  -BaseExposure 0.6 `
  -SentimentScale 0.2 `
  -SentimentSmoothAlpha 0.2
```

ClickHouse 密码建议通过环境变量传入：

```powershell
$env:CLICKHOUSE_PASSWORD = "<你的 ClickHouse 密码>"
```

也可以在项目根目录创建本地 `.env` 文件，脚本会自动读取：

```text
CLICKHOUSE_PASSWORD=<你的 ClickHouse 密码>
```

`.env` 已加入 `.gitignore`，不会提交到 Git。

## 分阶段运行命令

如果不想使用一键脚本，可以分阶段执行：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli clean --input data/ods/stock_daily.parquet --output-dir data
.\.venv\Scripts\python.exe -m quant_data.cli quality --output-dir data
.\.venv\Scripts\python.exe -m quant_data.cli factors --output-dir data
.\.venv\Scripts\python.exe -m quant_data.cli evaluate --output-dir data --factor-name momentum_20d_zscore
.\.venv\Scripts\python.exe -m quant_data.cli backtest --output-dir data --factor-name momentum_20d_zscore
.\.venv\Scripts\python.exe -m quant_data.cli sensitivity --output-dir data
.\.venv\Scripts\python.exe -m quant_data.cli cost-sensitivity --output-dir data --factor-name momentum_20d_zscore
```

批量评估和回测多个因子：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli factor-suite `
  --output-dir data `
  --factor-names momentum_20d,reversal_5d,volatility_20d,volume_ratio_5d,ma_bias_20d,momentum_20d_zscore,reversal_5d_zscore,volatility_20d_zscore,volume_ratio_5d_zscore,ma_bias_20d_zscore `
  --horizon 5 `
  --groups 5 `
  --top-quantile 0.1 `
  --rebalance-interval 20 `
  --factor-direction top
```

## 输出文件

```text
data/ods/stock_daily.parquet
data/dwd/stock_daily.parquet
data/dim/trade_calendar.parquet
data/dim/stock_basic.parquet
data/dim/hs300_index.parquet
data/reports/ingestion_report.parquet
data/reports/ingestion_runs.parquet
data/reports/data_quality_report.parquet
data/ads/factor_wide_daily.parquet
data/ads/market_sentiment_daily.parquet
data/ads/factor_eval_<factor_name>.parquet
data/ads/backtest_daily_<factor_name>.parquet
data/ads/backtest_metrics_<factor_name>.json
data/ads/factor_yearly_summary.parquet
data/ads/factor_rolling_summary.parquet
data/ads/parameter_sensitivity.parquet
data/ads/cost_sensitivity.parquet
```

字段说明见：[数据说明文档](docs/data_dictionary.zh-CN.md)

数据库查询接口说明见：[数据库查询接口说明](docs/query_interface.zh-CN.md)

## 写入 ClickHouse

如果本地 ClickHouse 已启动，可以把 Parquet 输出写入数据库：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli load-clickhouse `
  --output-dir data `
  --factor-name momentum_20d_zscore `
  --host 127.0.0.1 `
  --port 8123 `
  --username default `
  --password <你的 ClickHouse 密码> `
  --database quant_data
```

导入后会创建或覆盖以下表：

```text
dim_trade_calendar
dim_stock_basic
dim_hs300_index
dwd_stock_daily
ads_factor_wide_daily
ads_market_sentiment_daily
ads_factor_eval
ads_backtest_daily
ads_factor_yearly_summary
ads_factor_rolling_summary
ads_parameter_sensitivity
ads_cost_sensitivity
ops_ingestion_report
ops_ingestion_runs
ops_data_quality_report
```

可以在数据库工具里执行：

```sql
SHOW TABLES;
SELECT count() FROM dwd_stock_daily;
SELECT * FROM ads_factor_wide_daily LIMIT 10;
SELECT * FROM ads_parameter_sensitivity ORDER BY sharpe DESC LIMIT 20;
SELECT * FROM ads_cost_sensitivity ORDER BY factor_name, cost_scenario;
```

更多监控 SQL 见：[ClickHouse 监控 SQL](docs/clickhouse_monitoring_queries.sql)

## 测试

安装开发依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

当前测试覆盖：

- 配置读取
- Parquet 读写
- 日线清洗
- 数据质量规则
- 基础因子计算
- 市场情绪因子
- 因子评估
- 简单回测
- 因子方向选择
- 持仓缓冲区
- smooth 情绪仓位
- 参数敏感性输出
- 成本敏感性输出
- ClickHouse 表加载映射
- Streamlit 看板数据构造
- CLI 串联流程

## 项目边界

- 当前回测是研究型简化回测，用于验证数据链路、因子评估和策略诊断流程，不代表真实交易系统。
- AkShare 实时可用性取决于外部数据源和网络环境。
- 当前股票池可重建为最新沪深 300 成分股，但没有完整还原历史成分股变化，长区间回测仍可能存在幸存者偏差。
- 停牌、涨跌停、交易成本和滑点处理是工程化近似，生产环境需要更严格的成交模型。
- `data/` 目录不提交到 Git，新环境需要重新运行流水线生成本地数据。
- Streamlit 看板面向本地分析和展示，不是多用户生产部署。

## 项目总结

本项目以本地量化数据平台为目标，将行情采集、数据治理、因子加工、因子评估、策略回测、数据库落库和可视化看板串联为可复用的数据流水线。整体设计重点放在数据链路的可追踪性、可验证性和可扩展性，而不是单一策略收益表现。

当前版本进一步补充了策略诊断能力：通过因子方向验证、持仓缓冲、参数敏感性、成本敏感性和平滑情绪择时，帮助判断回测结果是否可信、是否过度依赖单一参数、是否被交易成本明显侵蚀。
