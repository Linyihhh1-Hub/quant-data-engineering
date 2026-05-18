# 数据说明文档

本文档说明当前量化数据工程项目中主要输入、输出文件的字段含义。项目采用本地 Parquet 文件作为中间数据存储，并可将部分结果写入 ClickHouse。

## 股票池文件

路径：`configs/symbols.csv`

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `symbol` | A 股股票代码，供 AkShare 采集接口使用，不带交易所后缀 | `000001` |
| `name` | 股票简称，主要用于人工阅读和维护股票池 | `平安银行` |

说明：

- `symbol` 是必填列。
- `name` 不是程序必需字段，只是方便维护。
- 当前股票池包含 20 只样例股票，覆盖银行、地产、消费、医药、券商、新能源、科技等方向。
- 批量真实采集时，如果采集报告出现 `FAILED`，可以对失败股票单独重试，再合并数据。

## 采集报告

路径：`data/reports/ingestion_report.parquet`

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `symbol` | 本次尝试采集的股票代码 | `000001` |
| `status` | 单只股票采集状态，取值为 `SUCCESS`、`FAILED`、`EMPTY` | `SUCCESS` |
| `row_count` | 该股票成功采集到的行数 | `242` |
| `message` | 失败或空数据时的说明；成功时通常为空字符串 | `AkShare returned empty data` |

状态说明：

- `SUCCESS`：成功采集到非空行情数据。
- `FAILED`：接口调用异常或字段不符合预期。
- `EMPTY`：接口正常返回，但没有行情行。

## ODS 原始日线行情

路径：`data/ods/stock_daily.parquet`

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `trade_date` | 交易日期 | `2024-01-02` |
| `symbol` | 股票代码，采集层保留原始 6 位代码 | `000001` |
| `open` | 开盘价 | `7.65` |
| `high` | 最高价 | `7.72` |
| `low` | 最低价 | `7.58` |
| `close` | 收盘价 | `7.65` |
| `volume` | 成交量，来自 AkShare 原始字段 | `1000000` |
| `amount` | 成交额，来自 AkShare 原始字段 | `100000000` |

说明：ODS 层只做字段名标准化，不做复杂业务清洗，方便保留接近源数据的形态。

## DWD 清洗后日线行情

路径：`data/dwd/stock_daily.parquet`

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `trade_date` | 标准化后的交易日期 | `2024-01-02` |
| `symbol` | 标准化后的股票代码，带交易所后缀 | `000001.SZ` |
| `open` | 数值化后的开盘价 | `7.65` |
| `high` | 数值化后的最高价 | `7.72` |
| `low` | 数值化后的最低价 | `7.58` |
| `close` | 数值化后的收盘价 | `7.65` |
| `volume` | 数值化后的成交量 | `1000000` |
| `amount` | 数值化后的成交额 | `100000000` |
| `return_1d` | 按股票分组计算的 1 日收益率，公式为 `close / close.shift(1) - 1` | `0.0123` |

说明：DWD 层会去重、排序、补交易所后缀，并计算后续因子和回测需要的基础收益字段。

## 数据质量报告

路径：`data/reports/data_quality_report.parquet`

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `rule_name` | 质量检查规则名称 | `primary_key_unique` |
| `status` | 检查结果，`PASS` 表示通过，`FAIL` 表示存在异常 | `PASS` |
| `failed_count` | 失败记录数量 | `0` |
| `failed_sample` | 少量失败样例，便于排查问题 | `[]` |

当前规则：

| 规则 | 含义 |
| --- | --- |
| `primary_key_unique` | `trade_date + symbol` 是否唯一 |
| `required_fields_not_null` | 核心价格和成交量字段是否为空 |
| `price_valid` | 价格是否非负、`close > 0`、`high >= low` |
| `volume_valid` | 成交量是否非负 |
| `date_completeness` | 每个交易日是否至少有指定数量股票 |
| `abnormal_return` | 单日收益率绝对值是否超过阈值 |

## ADS 因子宽表

路径：`data/ads/factor_wide_daily.parquet`

| 字段 | 含义 | 计算逻辑 |
| --- | --- | --- |
| `trade_date` | 交易日期 | - |
| `symbol` | 带交易所后缀的股票代码 | - |
| `momentum_20d` | 20 日动量因子 | `close / close.shift(20) - 1` |
| `reversal_5d` | 5 日反转因子 | `-1 * (close / close.shift(5) - 1)` |
| `volatility_20d` | 20 日波动率因子 | 1 日收益率的 20 日滚动标准差 |
| `volume_ratio_5d` | 5 日量比因子 | `volume / rolling_mean(volume, 5)` |
| `ma_bias_20d` | 20 日均线偏离因子 | `close / rolling_mean(close, 20) - 1` |

说明：所有滚动计算都按 `symbol` 分组，避免不同股票之间的数据串线。

## 因子评估表

路径：`data/ads/factor_eval_<factor_name>.parquet`

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `trade_date` | 评估日期 | `2024-02-01` |
| `factor_name` | 被评估的因子名称 | `momentum_20d` |
| `ic` | 因子值与未来收益的截面 Pearson 相关系数 | `0.35` |
| `rank_ic` | 因子排名与未来收益排名的截面相关系数 | `0.40` |
| `top_group_return` | 高因子组未来收益均值 | `0.018` |
| `bottom_group_return` | 低因子组未来收益均值 | `-0.006` |
| `long_short_return` | 多空收益，等于 `top_group_return - bottom_group_return` | `0.024` |

说明：股票池数量较少时，`--groups` 不宜设置过大。例如 20 只股票可以使用 `--groups 5`，3 只股票应使用 `--groups 3`。

## 回测日表

路径：`data/ads/backtest_daily_<factor_name>.parquet`

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `trade_date` | 回测日期 | `2024-01-02` |
| `portfolio_value` | 策略组合净值，初始值为 1.0 | `1.052` |
| `benchmark_value` | 简化基准净值，当前使用股票池等权收益 | `1.031` |
| `daily_return` | 策略组合当日收益率 | `0.004` |
| `benchmark_return` | 基准当日收益率 | `0.002` |
| `drawdown` | 策略当前回撤，等于 `portfolio_value / 历史最高净值 - 1` | `-0.08` |

说明：当前回测是简化版，主要用于展示因子数据链路和结果产出，不等同于可实盘交易策略。

## 回测指标

路径：`data/ads/backtest_metrics_<factor_name>.json`

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `total_return` | 全区间累计收益率 | `0.25` |
| `annualized_return` | 年化收益率，按 252 个交易日估算 | `0.28` |
| `max_drawdown` | 最大回撤，通常为负数 | `-0.12` |
| `sharpe` | 夏普比率，衡量单位波动下的收益表现 | `1.20` |
| `turnover` | 调仓换手累计值，越高表示交易越频繁 | `8.0` |

## ClickHouse 表

当前加载命令会写入以下 4 张表：

| 表名 | 对应本地文件 | 含义 |
| --- | --- | --- |
| `dwd_stock_daily` | `data/dwd/stock_daily.parquet` | 清洗后日线行情 |
| `ads_factor_wide_daily` | `data/ads/factor_wide_daily.parquet` | 因子宽表 |
| `ads_factor_eval` | `data/ads/factor_eval_<factor_name>.parquet` | 因子评估结果 |
| `ads_backtest_daily` | `data/ads/backtest_daily_<factor_name>.parquet` | 回测日度结果 |

采集报告和数据质量报告目前保存在本地 Parquet 文件中，后续可以继续扩展为 ClickHouse 表，便于做监控看板。
