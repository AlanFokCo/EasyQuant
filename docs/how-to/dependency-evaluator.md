# 运行 eqlib 对抗性依赖审查

`eqlib` 内置 evaluator 会从依赖、wheel 元数据、离线契约、性能基线和受限的在线数据契约五个方向检查发布质量。它会同时生成供人阅读的 Markdown 与供 CI 消费的 JSON 证据。

## 运行离线审查

在仓库根目录、使用 Python 3.10 或更新版本运行：

```bash
python scripts/evaluate_eqlib_dependencies.py \
  --profile offline --strict --output artifacts/eqlib-evaluator
```

产物为 `artifacts/eqlib-evaluator/report.md` 和 `report.json`。`--strict` 会让 P0/P1 发现以非零状态退出；P2（例如没有可比性能基线）仍会记录，但不会阻断提交。

离线契约明确排除 `pytest.mark.network`，因此不访问行情提供方。它覆盖导入、行情适配器边界、交易日历、组合风控、统计指标和机器学习预处理。

## 运行受限在线审查

在线契约仅运行明确标记为 `network` 的测试：

```bash
python scripts/evaluate_eqlib_dependencies.py \
  --profile live --output artifacts/eqlib-evaluator-live
```

该模式为提供方测试设置 `EQLIB_EVALUATOR_LIVE=1`，总时限为 90 秒。数据源不可用或超时会记为 `DATA-190`、状态为 `unavailable`，不会把网络故障误判为产品逻辑通过。GitHub Actions 在工作日定时和手动触发时运行此模式；普通 push/PR 只运行严格离线门禁。

## 解读发现

| 严重度 | 含义 | 严格离线门禁 |
| --- | --- | --- |
| P0 | 错误结果、不可安装或数据完整性风险 | 阻断 |
| P1 | 可靠性、契约或可重复性风险 | 阻断 |
| P2 | 性能、可观测性或暂不可用的辅助证据 | 记录，不阻断 |

报告中的 `evidence` 保留命令、退出码、失败 pytest node id 和有界日志。不要只看报告摘要；修复后应重新运行同一 profile。

## 更新锁文件

Python 3.10 的四目标哈希锁及其已检查的 resolver 证据位于 `requirements/`。锁文件不能手工修改；请按仓库根目录的 `requirements/README.md` 的生成、哈希补全和目标验证步骤更新。更新后至少运行严格离线 evaluator，并在原生 Linux Python 3.10 上执行锁文件的严格下载验证。

## CI 行为

`.github/workflows/eqlib-evaluator.yml` 在 Ubuntu 的 Python 3.10 与 3.12 上运行严格离线审查并上传报告；定时/手动 live job 上传在线报告。普通测试工作流以 `-m "not network"` 排除真实提供方调用，避免网络波动影响可重复测试。
