# 量化数据工程项目

这是一个面向求职展示的 A 股量化数据工程项目，重点不是追求策略收益，而是展示完整的数据链路建设能力：数据清洗、质量校验、因子计算、因子评估和简单回测。

## 项目目标

构建一条本地可运行的数据工程流水线：

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
```

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

### 5\. 简单回测

模块：`src/quant\_data/backtest/simple.py`

回测规则：

* 在调仓日按因子值选择 top 分位股票
* 等权持仓
* 支持交易成本
* 使用全市场等权收益作为简化基准
* 输出组合净值、基准净值、日收益、回撤

指标：

```text
total\_return, annualized\_return, max\_drawdown, sharpe, turnover
```

## CLI 串联流程

CLI 的作用是把各个模块串成可执行的数据流水线。每个命令读取上一阶段的 Parquet 输出，再写入下一阶段结果。

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
  --report data/reports/ingestion_report.parquet
```

股票池文件必须包含 `symbol` 列，可以额外包含 `name` 等说明字段。采集报告会记录每只股票的采集结果：

```text
symbol, status, row_count, message
```

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
  --rebalance-interval 20
```

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

导入后会创建 4 张表：

```text
dwd_stock_daily
ads_factor_wide_daily
ads_factor_eval
ads_backtest_daily
```

可以在数据库工具里执行：

```sql
SHOW TABLES;
SELECT count() FROM dwd_stock_daily;
SELECT * FROM ads_factor_wide_daily LIMIT 10;
```

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

## 简历描述参考

构建 A 股量化因子数据工程项目，基于 Python/pandas/Parquet 实现 ODS-DWD-ADS 分层数据链路，完成日线行情清洗、数据质量校验、基础因子宽表构建、IC/RankIC/分组收益评估和简单因子回测，并通过 CLI 串联为可复用的数据流水线。


