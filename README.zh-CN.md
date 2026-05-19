# 量化数据工程项目

这是一个本地可运行的 A 股量化数据工程项目，围绕行情采集、数据分层、质量校验、因子计算、因子评估、策略回测、ClickHouse 入库和 Streamlit 可视化看板，构建一条完整的量化数据处理链路。

## 项目亮点

* **完整数据链路**：覆盖 ODS 原始行情、DWD 清洗日线、ADS 因子宽表、评估结果和回测结果。
* **真实数据接入**：支持通过 AkShare 采集 A 股日线行情，并支持股票池文件、重试、增量采集和采集日志。
* **质量可观测**：内置主键唯一性、必填字段、价格合法性、成交量、日期完整性和异常收益等质量规则。
* **因子研究闭环**：实现基础量价因子、市场情绪因子、IC/RankIC、分组收益和 Top-Bottom 收益评估。
* **回测约束更贴近市场**：支持防未来函数、调仓周期、交易成本、佣金、滑点、印花税、停牌和涨跌停交易约束。
* **工程化输出**：提供 CLI 一键流水线、ClickHouse 写入、查询接口、Streamlit 看板和 pytest 自动化测试。

## 数据链路

项目构建的数据工程流水线：

```text
ODS 原始行情数据
-> DWD 清洗后日线数据
-> 数据质量报告
-> ADS 因子宽表
-> 因子有效性评估
-> 简单因子回测
```

## 技术栈

```text
Python
pandas / numpy
PyArrow / Parquet
pytest
argparse CLI
Streamlit
```

## 快速运行

日常更新和完整重跑推荐直接执行一键脚本：

```powershell
.\scripts\run_daily_pipeline.ps1 `
  -StartDate 20240101 `
  -EndDate 20241231
```

这个命令会按 `configs/symbols.csv` 股票池执行增量采集，然后自动完成清洗、质量检查、因子计算、因子评估、回测和 ClickHouse 写入。

如果要把股票池扩展为沪深 300 成分股，可以先生成股票池：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli build-hs300-symbols `
  --output configs/symbols.csv
```

也可以在一键脚本里自动生成：

```powershell
.\scripts\run_daily_pipeline.ps1 `
  -StartDate 20240101 `
  -EndDate 20241231 `
  -BuildHs300Symbols $true
```

脚本会同步生成 `dim_trade_calendar` 和 `dim_stock_basic` 两张维表。当前回测已加入防未来函数处理：当天因子信号只能在下一交易日执行，并支持停牌、涨停不能买入、跌停不能卖出、佣金、滑点和印花税等约束。

## 当前功能

### 1\. 日线数据清洗

模块：`src/quant\_data/cleaning/daily.py`

功能：

* 标准化交易日期
* 标准化 A 股股票代码后缀
* 转换 OHLCV 数值字段
* 去重
* 按股票计算 1 日收益率

### 2\. 数据质量检查

模块：`src/quant\_data/quality/rules.py`

检查规则：

* 主键唯一性：`trade\_date + symbol`
* 必填字段非空：`open/high/low/close/volume`
* 价格合法性：价格非负、`close > 0`、`high >= low`
* 成交量合法性：`volume >= 0`
* 日期完整性：每个交易日至少有指定股票数量
* 异常收益：`abs(return\_1d)` 超过阈值

输出字段：

```text
rule\_name, status, failed\_count, failed\_sample
```

### 3\. 基础因子计算

模块：`src/quant\_data/factors/baseline.py`

已实现因子：

```text
momentum\_20d
reversal\_5d
volatility\_20d
volume\_ratio\_5d
ma\_bias\_20d
```

输出因子宽表：

```text
trade\_date, symbol, momentum\_20d, reversal\_5d, volatility\_20d, volume\_ratio\_5d, ma\_bias\_20d
```

### 4\. 因子评估

模块：`src/quant\_data/evaluation/factor.py`

评估指标：

* 未来 N 日收益
* IC
* RankIC
* 顶部分组收益
* 底部分组收益
* 多空收益

输出字段：

```text
trade\_date, factor\_name, ic, rank\_ic, top\_group\_return, bottom\_group\_return, long\_short\_return
```

### 5\. 行情衍生市场情绪因子

模块：`src/quant_data/factors/sentiment.py`

已实现：

* 市场宽度：上涨股票占比、强势股票占比、弱势股票占比
* 成交活跃度：成交额放大倍数、成交量放大倍数
* 赚钱效应：上涨股票平均收益与下跌股票平均跌幅对比
* 综合情绪分数：多个子因子的 60 日滚动 z-score 合成

输出市场情绪表：

```text
data/ads/market_sentiment_daily.parquet
```

核心情绪字段也会按 `trade_date` 合并回 `data/ads/factor_wide_daily.parquet`。

### 6\. 简单回测

模块：`src/quant\_data/backtest/simple.py`

回测规则：

* 在调仓日按因子值选择 top 分位股票
* 等权持仓
* 支持交易成本
* 支持情绪择时：市场情绪分数低于阈值时降低目标仓位
* 使用全市场等权收益作为简化基准
* 输出组合净值、基准净值、日收益、回撤、目标仓位

指标：

```text
total\_return, annualized\_return, max\_drawdown, sharpe, turnover, total\_cost, average\_exposure
```

情绪择时默认关闭。开启后，回测会使用调仓信号日的 `market_sentiment_score` 判断下一交易日目标仓位，避免使用未来数据。例如：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli backtest `
  --output-dir data `
  --factor-name momentum_20d `
  --sentiment-threshold 0 `
  --weak-sentiment-exposure 0.3 `
  --normal-exposure 1.0
```

### 7\. Streamlit 展示看板

模块：`src/quant_data/dashboard/app.py`

看板包含 3 个核心页面：

* 数据链路概览：展示 ODS/DWD/ADS 行数、股票数量、日期范围、采集失败股票和质量异常规则
* 因子有效性评估：展示 IC 均值、RankIC 均值、正 IC 占比、ICIR、IC/RankIC 曲线和分组收益
* 策略回测表现：展示收益风险指标、策略净值、基准净值、回撤曲线和情绪择时仓位曲线

启动方式：

```powershell
.\.venv\Scripts\streamlit.exe run src\quant_data\dashboard\app.py
```

默认读取 `data` 目录下的 Parquet 和 JSON 结果，可以在页面左侧修改数据目录。

## CLI 串联流程

CLI 的作用是把各个模块串成可执行的数据流水线。每个命令读取上一阶段的 Parquet 输出，再写入下一阶段结果。

日常运行推荐使用一键脚本：

```powershell
.\scripts\run_daily_pipeline.ps1 `
  -StartDate 20240101 `
  -EndDate 20241231
```

脚本会执行：增量采集、清洗、质量检查、因子计算、因子评估、回测，并在配置了 ClickHouse 密码时自动写入 ClickHouse。ClickHouse 密码建议通过环境变量传入：

如果要在一键脚本中开启情绪择时回测，可以增加以下参数：

```powershell
.\scripts\run_daily_pipeline.ps1 `
  -StartDate 20240101 `
  -EndDate 20241231 `
  -SentimentThreshold 0 `
  -WeakSentimentExposure 0.3 `
  -NormalExposure 1.0
```

```powershell
$env:CLICKHOUSE_PASSWORD = "<你的 ClickHouse 密码>"
```

也可以在项目根目录创建本地 `.env` 文件，脚本会自动读取：

```text
CLICKHOUSE_PASSWORD=<你的 ClickHouse 密码>
```

`.env` 已加入 `.gitignore`，不会提交到 git。

接入 AkShare 真实 A 股日线数据：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli ingest-akshare `
  --symbols 000001,600000,600519 `
  --start-date 20240101 `
  --end-date 20241231 `
  --adjust qfq `
  --output data/ods/stock_daily.parquet
```

也可以使用 CSV 股票池文件批量采集，示例文件为 `configs/symbols.csv`：

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
  --incremental `
  --run-log data/reports/ingestion_runs.parquet
```

股票池文件必须包含 `symbol` 列，可以额外包含 `name` 等说明字段。采集报告会记录每只股票的采集结果：

```text
symbol, status, row_count, message
```

`--retries` 和 `--retry-wait-seconds` 用于处理外部行情接口的短暂网络失败。`--incremental` 会基于已有 ODS 文件判断每只股票的最新日期，只补采缺失日期；`--run-log` 会记录每次采集任务的运行汇总。批量采集时建议开启重试，失败股票可以根据采集报告单独补采。

这个命令会调用 AkShare 的 A 股历史行情接口，生成项目后续流水线需要的 ODS 文件：

```text
data/ods/stock_daily.parquet
data/reports/ingestion_report.parquet
```

完整运行：

```powershell
.\\.venv\\Scripts\\python.exe -m quant\_data.cli run-all `
  --input data/ods/stock\_daily.parquet `
  --output-dir data `
  --factor-name momentum\_20d `
  --horizon 5 `
  --groups 5 `
  --top-quantile 0.1 `
  --rebalance-interval 20 `
  --sentiment-threshold 0 `
  --weak-sentiment-exposure 0.3 `
  --normal-exposure 1.0
```

批量评估和回测所有基础因子：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli factor-suite `
  --output-dir data `
  --factor-names momentum_20d,reversal_5d,volatility_20d,volume_ratio_5d,ma_bias_20d `
  --horizon 5 `
  --groups 5 `
  --top-quantile 0.1 `
  --rebalance-interval 20 `
  --sentiment-threshold 0 `
  --weak-sentiment-exposure 0.3 `
  --normal-exposure 1.0
```

一键脚本 `scripts/run_daily_pipeline.ps1` 默认也会执行多因子评估和回测，并在 Streamlit 看板里生成多因子对比表。

也可以分阶段运行：

```powershell
.\\.venv\\Scripts\\python.exe -m quant\_data.cli clean --input data/ods/stock\_daily.parquet --output-dir data
.\\.venv\\Scripts\\python.exe -m quant\_data.cli quality --output-dir data
.\\.venv\\Scripts\\python.exe -m quant\_data.cli factors --output-dir data
.\\.venv\\Scripts\\python.exe -m quant\_data.cli evaluate --output-dir data --factor-name momentum\_20d
.\\.venv\\Scripts\\python.exe -m quant\_data.cli backtest --output-dir data --factor-name momentum\_20d
```

## 输出文件

```text
data/dwd/stock\_daily.parquet
data/reports/data\_quality\_report.parquet
data/ads/factor\_wide\_daily.parquet
data/ads/factor\_eval\_<factor\_name>.parquet
data/ads/backtest\_daily\_<factor\_name>.parquet
data/ads/backtest\_metrics\_<factor\_name>.json
```

字段说明见：[数据说明文档](docs/data_dictionary.zh-CN.md)

数据库查询接口说明见：[数据库查询接口说明](docs/query_interface.zh-CN.md)

## 写入 ClickHouse

如果本地 ClickHouse 已启动，可以把 Parquet 输出写入数据库：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli load-clickhouse `
  --output-dir data `
  --factor-name momentum_20d `
  --host 127.0.0.1 `
  --port 8123 `
  --username default `
  --password <你的 ClickHouse 密码> `
  --database quant_data
```

导入后会创建 9 张表：

```text
dwd_stock_daily
dim_trade_calendar
dim_stock_basic
ads_factor_wide_daily
ads_market_sentiment_daily
ads_factor_eval
ads_backtest_daily
ops_ingestion_report
ops_ingestion_runs
ops_data_quality_report
```

可以在数据库工具里执行：

```sql
SHOW TABLES;
SELECT count() FROM dwd_stock_daily;
SELECT * FROM ads_factor_wide_daily LIMIT 10;
```

更多监控 SQL 见：[ClickHouse 监控 SQL](docs/clickhouse_monitoring_queries.sql)

## 测试

安装开发依赖：

```powershell
.\\.venv\\Scripts\\python.exe -m pip install -e ".\[dev]"
```

运行测试：

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -q
```

当前测试覆盖：

* 配置读取
* Parquet 读写
* 日线清洗
* 数据质量规则
* 基础因子计算
* 因子评估
* 简单回测
* CLI 串联流程

## 项目总结

本项目以本地量化数据平台为目标，将行情采集、数据治理、因子加工、因子评估、策略回测、数据库落库和可视化看板串联为可复用的数据流水线。整体设计重点放在数据链路的可追踪性、可验证性和可扩展性，而不是单一策略收益表现。


