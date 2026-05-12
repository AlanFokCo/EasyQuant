# Tutorial 00: 环境与第一次运行

> 在按顺序阅读 [Tutorial 01](01_quant_basics.md) 之前，请先完成本节：保证 Python 环境、`eqlib` 安装与一次成功回测，避免后续教程中的代码无法运行。

**没有 Python 基础？** 先阅读 [前置知识：Python 基础与环境配置](prerequisites/python_basics.md)。  
**不了解技术指标？** 阅读 [前置知识：技术分析基础概念](prerequisites/technical_concepts.md)。  
**不熟悉 A 股规则？** 阅读 [前置知识：A 股市场基础知识](prerequisites/ashare_knowledge.md)。

---

## 1. 你需要什么环境？

| 项目 | 要求 |
|------|------|
| Python | **3.10、3.11 或 3.12**（`eqlib` 在 `pyproject.toml` 中声明 `requires-python >= 3.10`） |
| 操作系统 | macOS / Linux / Windows 均可 |
| 网络 | 首次拉取行情依赖 `akshare` 在线接口，需能访问外网或数据源 |

---

## 2. 安装 eqlib（推荐）

在克隆下来的仓库**根目录**执行（会一并安装 `akshare`、`pandas` 等依赖）：

```bash
cd EasyQuant
python3 -m venv .venv          # 可选，但强烈推荐
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install .
# 开发调试可选用：pip install -e .
```

验证：

```bash
python -c "from importlib.metadata import version; print('eqlib', version('eqlib'))"
```

若 `pip install .` 报错，请先阅读 [**常见问题 FAQ**](../doc/FAQ.md) 中的「安装与环境」。

---

## 3. 第一次跑示例回测

在仓库根目录执行：

```bash
python examples/03_run_backtest.py
```

脚本会下载（或更新）数据并运行回测。结束后终端会打印 `reports/` 下的 **PNG、HTML、Markdown、JSON** 路径。

用浏览器打开其中的 **`.html` 文件`**，从上到下浏览：指标卡片 → 图表 → 成交与持仓。各字段含义见 [**报告与指标详解**](../doc/reports_and_metrics.md)。

与 **`reports/`** 中已保存的示例导出如何对照，见 **[`reports/README.md`](../reports/README.md)**（推荐与 [`tutorials/assets/example_report_html_19_localdata.png`](assets/example_report_html_19_localdata.png) 及 Tutorial 03 配图一起阅读）。

---

## 4. 可选：只测数据接口

若你想先确认网络与数据是否正常，可运行：

```bash
python examples/01_fetch_data.py
```

该脚本侧重演示 `get_price`、`fetch_stock_data` 等数据 API，不涉及完整回测报告。

---

## 5. 推荐：先下载目标股票到本地，再做快速回测验证

如果你已经有明确的研究标的，建议先把数据下载到本地，再用 `use_local=True` 做快速回测，这样可以显著减少网络波动带来的不确定性。

```bash
python - <<'PY'
from eqlib import set_local_data_dir, save_stock_local, list_local_stocks

set_local_data_dir('/home/user/eqlib_data')  # 推荐绝对路径，便于多项目复用
targets = ['601390', '600519', '000858', '000300.XSHG']  # 含基准

for sec in targets:
    path = save_stock_local(sec, start_date='2020-01-01', end_date='2024-12-31')
    print(sec, '->', path)

print('local files:', list_local_stocks())
PY
```

然后运行任一回测脚本时开启本地模式：

```python
result = run_strategy(
    initialize,
    start_date='2024-01-01',
    end_date='2024-12-31',
    securities=['601390'],
    use_local=True,
)
```

建议先跑 [`examples/19_local_data_backtest.py`](../examples/19_local_data_backtest.py) 做离线流程验证。

> 提示：本地已下载数据的日期区间应覆盖你的回测区间；若回测起止超出本地文件范围，请先补齐对应日期数据再运行。

更多接口说明见：

- [用户手册 7.11：下载与加载本地 CSV](../doc/user_guide.md#711-下载与加载本地-csv)
- [API 参考 8：缓存 API](../doc/api_reference.md#8-缓存-api)
- [FAQ：首次回测慢或卡住](../doc/FAQ.md#q-首次回测很慢或卡住)

---

## 6. 教程、示例与「正式文档」怎么配合？

| 资源 | 用途 |
|------|------|
| `tutorials/`（本目录） | 按主题循序渐进：**为什么这样写、常见坑** |
| `examples/` | **可复制运行的脚本**，对照 [`Examples.md`](../examples/Examples.md) 索引 |
| `doc/README.md` | **文档中心**：用户手册、API 全表、FAQ、报告解读的入口 |

---

## 7. 下一步

当你已能成功运行 `examples/03_run_backtest.py` 并打开 HTML 报告后，请继续：

**[Tutorial 01: 什么是量化交易策略](01_quant_basics.md)** → [Tutorial 02: 写第一个策略](02_first_strategy.md)。
