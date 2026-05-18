# 数据库查询接口说明

本文档说明如何在 Python 脚本或 Notebook 中调用 ClickHouse 数据查询接口。接口模块位于：

```text
src/quant_data/service/query.py
```

它的作用是把常用 SQL 封装成稳定函数，减少策略研究或数据分析时重复手写 SQL。

## 连接 ClickHouse

如果项目根目录 `.env` 中已经配置了 ClickHouse 密码，可以在 Python 里读取后创建连接：

```python
from pathlib import Path

from quant_data.service.query import ClickHouseConfig, create_clickhouse_client


def read_clickhouse_password() -> str:
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("CLICKHOUSE_PASSWORD="):
            return line.split("=", 1)[1].strip()
    return ""


client = create_clickhouse_client(
    ClickHouseConfig(password=read_clickhouse_password())
)
```

## 查询单只股票日线行情

```python
from quant_data.service.query import get_stock_daily

df = get_stock_daily(
    client,
    symbol="000001.SZ",
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

返回字段：

```text
trade_date, symbol, open, high, low, close, volume, amount, return_1d
```

## 查询多只股票日线行情

```python
from quant_data.service.query import get_stock_daily_panel

df = get_stock_daily_panel(
    client,
    symbols=["000001.SZ", "600519.SH"],
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

## 查询因子值

```python
from quant_data.service.query import get_factor_values

df = get_factor_values(
    client,
    factor_name="momentum_20d",
    start_date="2024-02-01",
    end_date="2024-12-31",
    symbols=["000001.SZ", "600519.SH"],
)
```

当前支持的因子名：

```text
momentum_20d
reversal_5d
volatility_20d
volume_ratio_5d
ma_bias_20d
```

说明：`factor_name` 会做白名单校验，避免把任意字符串拼接进 SQL 字段名。

## 查询因子评估结果

```python
from quant_data.service.query import get_factor_eval

df = get_factor_eval(client, factor_name="momentum_20d")
```

返回字段：

```text
trade_date, factor_name, ic, rank_ic, top_group_return, bottom_group_return, long_short_return
```

## 查询市场情绪因子

```python
from quant_data.service.query import get_market_sentiment

df = get_market_sentiment(
    client,
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

返回市场宽度、成交活跃度、赚钱效应和综合情绪分数等市场级字段。

## 查询 OPS 监控信息

查询最近一次采集任务：

```python
from quant_data.service.query import get_latest_ingestion_run

df = get_latest_ingestion_run(client)
```

查询采集失败股票：

```python
from quant_data.service.query import get_failed_ingestion_symbols

df = get_failed_ingestion_symbols(client)
```

查询质量检查失败规则：

```python
from quant_data.service.query import get_quality_failures

df = get_quality_failures(client)
```

## 面向岗位的价值

这些函数对应量化数据开发岗位中的“数据库接口函数”能力：

```text
策略研究员只需要传股票、日期、因子名等业务参数，就能拿到 pandas DataFrame；
底层 ClickHouse 连接、SQL、字段选择、排序和监控表查询由接口层统一封装。
```
