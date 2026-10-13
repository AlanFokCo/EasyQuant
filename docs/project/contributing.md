# 贡献指南

欢迎参与 EasyQuant：bug 报告、功能建议、文档改进、代码贡献都可以。

## 贡献方式

### 报告 Bug

到 GitHub Issues 提交，请带上：

- 问题描述
- 复现步骤（能给最小示例最好）
- 期望行为 vs 实际行为
- Python 版本与 `eqlib` 版本
- 相关日志或报错信息

### 提功能建议

先开 Issue 讨论，再提 PR。提前对齐范围和设计，免得白写。

### 提交 Pull Request

1. Fork 仓库，建功能分支（`git checkout -b feature/my-feature`）
2. 改代码——沿用现有代码风格
3. 代码改动要在 `tests/` 里补或更新测试
4. 跑测试：`python -m pytest tests/`
5. 提交信息用约定前缀（见下文）
6. 推送并向 `main` 提 PR

## 开发环境

```bash
pip install -e ".[dev]"
python -m pytest tests/
```

## 代码风格

- 遵循 PEP 8，写类型标注
- 导入要显式——示例里不要 `from eqlib import *`
- 公开 API 函数写 docstring
- `eqlib/__init__.py` 的导出标注 `STABLE` / `EXPERIMENTAL` / `DEPRECATED`
- 用 `eqlib/constants.py` 里的共享常量（`RISK_FREE_RATE = 0.03`、`TRADING_DAYS_PER_YEAR = 244`），不要硬编码
- Pre-commit 钩子会检查行尾空白、文件末尾换行、YAML/TOML 语法

## 文档

文档在 `docs/`，中英双语：每个 `*.md` 都有一个对应的 `*.en.md`。

- 改 `docs/**/*.md` 时，同一个 PR 里同步更新对应的 `.en.md`
- 提交前跑 `python scripts/check_doc_sync.py`——它检查翻译配对、失效的示例引用、交易成本数字是否与 `examples/_defaults.py` 一致
- CI 跑 `mkdocs build --strict`；本地可用 `mkdocs serve` 预览
- 改 `eqlib/` 公开 API 时，要连带更新受影响的示例、教程（双语）和 `docs/reference/`

## 示例

在 `examples/` 下新增或修改示例时：

- 交易成本与股票代码统一用 `examples/_defaults.py`（印花税 0.05%、佣金 0.025%、最低 5 元）
- 模块 docstring 写清编号、标题、说明、教学目标
- 加 `if __name__ == "__main__":` 守卫
- 两个索引都要更新：`examples/README.md` 和 `docs/examples/index.md`（含 `.en.md`）

## 提交信息

用约定前缀：

| 前缀 | 用途 |
|------|------|
| `docs:` | 文档（永远同时更新 `.md` 和 `.en.md`） |
| `fix:` | Bug 修复 |
| `feat:` | 新功能或新示例 |
| `chore:` | 清理、重组 |
| `refactor:` | 不改变行为的重构 |

## 许可证

贡献即表示你同意所提交内容以 MIT License 发布。
