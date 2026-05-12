<p align="center">
<a href="https://github.com/AlanFokCo/EasyQuant"><img src="assets/logo.svg" width="240" alt="EasyQuant"/></a>
</p>

# EasyQuant 文档中心

面向 **中国 A 股** 的本地回测与策略开发。核心包名为 **`eqlib`**（与仓库名 EasyQuant 对应）。

---

## 建议阅读顺序

| 顺序 | 文档 | 说明 |
|------|------|------|
| 1 | [用户手册](user_guide.md) | 安装、策略骨架、`run_strategy` / `run_backtest`、数据与报告概览 |
| 2 | [环境、报告与指标详解](reports_and_metrics.md) | 打开 HTML/PNG、**第 2.8 节 HTML 对照走读**、`analyze_returns` 全字段 |
| 3 | [常见问题 FAQ](FAQ.md) | 安装失败、数据下载、回测无图、性能与排错 |
| 4 | [API 速查索引](api_index.md) | 按主题跳转 `api_reference.md` 章节 |
| 5 | [API 参考（完整）](api_reference.md) | 全部公开 API 的参数与示例 |
| 6 | [工具库参考](utils_reference.md) | `eqlib.utils` 指标与公式说明 |
| 7 | [PTrade/QMT 适配器](ptrade_adapter.md) | 导出到券商实盘环境 |

**教程（分步学习）：** 仓库根目录下 [`tutorials/`](../tutorials/README.md)，建议从「环境与第一次运行」开始。

**可运行示例：** [`examples/Examples.md`](../examples/Examples.md)。

**示例回测产物：** [`reports/README.md`](../reports/README.md)（说明 `reports/` 下 HTML/PNG 等与各 `examples/` 脚本的对应关系；目录内其它文件默认不提交 Git）。

---

## 新手 15 分钟验证清单

```bash
cd EasyQuant
pip install .
python -c "from eqlib import *; print('eqlib OK')"
python examples/03_run_backtest.py
```

然后在 `reports/` 打开最新 `.html` 文件，确认：收益曲线、回撤曲线、交易记录都能显示。

若要做额外自检：

```bash
python examples/01_fetch_data.py
pip install -e ".[dev]"
python -m pytest tests/
```

---

## 快速命令

```bash
# Python 3.10+ 必填（见 pyproject.toml）
cd EasyQuant
pip install .
# 可选：pip install -e .   # 开发模式

python examples/03_run_backtest.py
# 在 reports/ 下查看生成的 .html / .png / .md / .json（说明见 reports/README.md）
```

---

## 本地预览文档站点

```bash
pip install -e ".[docs]"
mkdocs serve
```

启动后访问 <http://127.0.0.1:8000>，用于预览 GitHub Pages 文档站点。

---

## 相关链接

- 项目说明（中文）：[`README_zh.md`](../README_zh.md)
- AI 优化约定：[`CLAUDE.md`](../CLAUDE.md)
- 本地数据快速验证：[`tutorials/00_environment_and_first_run.md`](../tutorials/00_environment_and_first_run.md)
