!!! tip "章节导航"

    [← 用户手册总览](index.md) · [上一章 §1](01_intro_scope.md) · [下一章 §3](03_quickstart_strategy.md)

---

## 2. 安装

**环境要求：Python 3.10 及以上**（见仓库 `pyproject.toml` 中 `requires-python`）。若使用 3.9 及以下，`pip install .` 会直接被拒绝。

```bash
# 推荐：在克隆的仓库根目录安装 eqlib（含全部依赖）
cd EasyQuant
pip install .
# 开发时可选用：pip install -e .

# 若仅想手动装依赖、再从源码路径导入（不推荐），可：
# pip install akshare pandas numpy matplotlib scipy
# pip install pyarrow   # 可选，更好的磁盘缓存性能
```

确认安装成功：

```python
from eqlib import *
print("eqlib OK")
```

更多排错见 [**常见问题 FAQ**](../FAQ.md) 与 [**文档中心**](../README.md)。
