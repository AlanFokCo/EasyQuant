!!! tip "章节导航"

    [← 用户手册总览](index.md) · [下一章 §1](01_intro_scope.md)

---

## 0. 新手先完成这 4 步

如果你是第一次接触 EasyQuant，请先完成以下最小闭环，再阅读后续章节：

1. 安装：
   ```bash
   pip install .
   ```
2. 验证导入：
   ```bash
   python -c "from eqlib import *; print('eqlib OK')"
   ```
3. 跑一次完整回测：
   ```bash
   python examples/03_run_backtest.py
   ```
4. 打开 `reports/` 下最新 `.html`，确认图表和指标正常显示。

可选测试：

```bash
python examples/01_fetch_data.py
pip install -e ".[dev]"
python -m pytest tests/
```
