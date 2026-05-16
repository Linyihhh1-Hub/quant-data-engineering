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

### 1. 日线数据清洗

模块：`src/quant_data/cleaning/daily.py`

功能：

- 标准化交易日期
- 标准化 A 股股票代码后缀
- 转换 OHLCV 数值字段
- 去重
- 按股票计算 1 日收益率

### 2. 数据质量检查

模块：`src/quant_data/quality/rules.py`

检查规则：

- 主键唯一性：`trade_date + symbol`
- 必填字段非空：`open/high/low/close/volume`
- 价格合法性：价格非负、`close > 0`、`high >= low`
- 成交量合法性：`volume >= 0`
- 日期完整性：每个交易日至少有指定股票数量
- 异常收益：`abs(return_1d)` 超过阈值

输出字段：

```text
rule_name, status, failed_count, failed_sample
```

### 3. 基础因子计算

模块：`src/quant_data/factors/baseline.py`

已实现因子：

```text
momentum_20d
reversal_5d
volatility_20d
volume_ratio_5d
ma_bias_20d
```

输出因子宽表：

```text
trade_date, symbol, momentum_20d, reversal_5d, volatility_20d, volume_ratio_5d, ma_bias_20d
```

### 4. 因子评估

模块：`src/quant_data/evaluation/factor.py`

评估指标：

- 未来 N 日收益
- IC
- RankIC
- 顶部分组收益
- 底部分组收益
- 多空收益

输出字段：

```text
trade_date, factor_name, ic, rank_ic, top_group_return, bottom_group_return, long_short_return
```

### 5. 简单回测

模块：`src/quant_data/backtest/simple.py`

回测规则：

- 在调仓日按因子值选择 top 分位股票
- 等权持仓
- 支持交易成本
- 使用全市场等权收益作为简化基准
- 输出组合净值、基准净值、日收益、回撤

指标：

```text
total_return, annualized_return, max_drawdown, sharpe, turnover
```

## CLI 串联流程

CLI 的作用是把各个模块串成可执行的数据流水线。每个命令读取上一阶段的 Parquet 输出，再写入下一阶段结果。

完整运行：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli run-all `
  --input data/ods/stock_daily.parquet `
  --output-dir data `
  --factor-name momentum_20d `
  --horizon 5 `
  --groups 5 `
  --top-quantile 0.1 `
  --rebalance-interval 20
```

也可以分阶段运行：

```powershell
.\.venv\Scripts\python.exe -m quant_data.cli clean --input data/ods/stock_daily.parquet --output-dir data
.\.venv\Scripts\python.exe -m quant_data.cli quality --output-dir data
.\.venv\Scripts\python.exe -m quant_data.cli factors --output-dir data
.\.venv\Scripts\python.exe -m quant_data.cli evaluate --output-dir data --factor-name momentum_20d
.\.venv\Scripts\python.exe -m quant_data.cli backtest --output-dir data --factor-name momentum_20d
```

## 输出文件

```text
data/dwd/stock_daily.parquet
data/reports/data_quality_report.parquet
data/ads/factor_wide_daily.parquet
data/ads/factor_eval_<factor_name>.parquet
data/ads/backtest_daily_<factor_name>.parquet
data/ads/backtest_metrics_<factor_name>.json
```

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
- 因子评估
- 简单回测
- CLI 串联流程

## 简历描述参考

构建 A 股量化因子数据工程项目，基于 Python/pandas/Parquet 实现 ODS-DWD-ADS 分层数据链路，完成日线行情清洗、数据质量校验、基础因子宽表构建、IC/RankIC/分组收益评估和简单因子回测，并通过 CLI 串联为可复用的数据流水线。
