# EasyQuant Phase 1: 回测科学性升级设计文档

**日期**: 2026-05-27
**阶段**: Phase 1
**目标**: 构建完整科学验证框架，建立对回测结果的信任

---

## 1. 项目背景

### 1.1 核心痛点

| 痛点 | 说明 |
|-----|------|
| 过拟合风险 | 策略回测表现好，实盘失效，担心参数是"调出来的" |
| 统计置信度不足 | 不知道回测结果是否只是运气（样本量小、时间窗口短） |
| 偏差未处理 | 幸存者偏差、前视偏差等可能导致结果虚高 |
| 风险度量过于简单 | 只有Sharpe和最大回撤，缺少专业风险指标 |
| 结果可信度担忧 | 无法确定回测结果是否可用于实盘决策参考 |

### 1.2 使用场景

- 模拟盘测试 → 实盘交易准备
- 需要高置信度指导真实资金配置
- 策略类型：单因子、多因子、择时、配对交易

### 1.3 成功标准

1. 所有计划功能实现并可用
2. 用现有策略验证后发现并修正过去未注意到的问题
3. 回测报告有足够统计证据（置信区间、显著性检验），可支持实盘决策
4. 与专业平台（JoinQuant、聚宽）对比验证，差异在合理范围

---

## 2. 整体架构

```
eqlib/
├── engine.py              # 现有回测引擎（保持不变）
├── data.py                # 数据层（保持不变）
├── trade.py               # 交易执行（保持不变）
├── attribution.py         # 归因分析（保持不变）
├── report.py              # 报告生成（保持不变）
│
├── scientific/            # ★ 新增科学验证层
│   ├── __init__.py            # 导出API
│   ├── overfitting.py         # 过拟合检测模块
│   ├── statistics.py          # 统计置信度模块
│   ├── bias.py                # 偏差检测与处理模块
│   ├── risk.py                # 扩展风险度量模块
│   ├── comparison.py          # 平台对比校验模块
│   ├── validation_runner.py   # 统一验证流程编排
│   └── report.py              # 科学验证报告生成
│
└── validation_config.py   # 验证参数配置（全局默认值）
```

### 2.1 设计原则

1. **零侵入** — 现有 `run_backtest()` API保持不变，科学验证作为可选增强层
2. **可组合** — 每个模块独立可用，也可通过 `validation_runner` 一键运行完整验证流程
3. **渐进启用** — 用户可选择启用哪些验证模块，避免计算资源爆炸

### 2.2 典型使用方式

```python
from eqlib import run_backtest, analyze_returns
from eqlib.scientific import validate_backtest, ValidationConfig

# 基础回测（现有方式，不变）
result = run_backtest(initialize, start_date='2024-01-01', end_date='2024-12-31')

# 科学验证增强（新功能）
validation_result = validate_backtest(
    result,
    config=ValidationConfig(
        overfitting=True,
        statistics=True,
        bias_check=True,
        risk_metrics='extended',
        comparison=True,
        n_simulations=1000
    )
)

# 查看验证报告
validation_result.summary()
validation_result.report_html('validation_report.html')
```

---

## 3. 过拟合检测模块 (`overfitting.py`)

### 3.1 目标

检测策略是否存在参数过拟合，评估参数稳健性。

### 3.2 核心功能

| 功能 | 说明 | 输出 |
|-----|------|------|
| Walk-forward分析 | 滚动窗口训练-测试，模拟真实使用 | 各窗口性能分布、衰减趋势 |
| 参数敏感性测试 | 扫描参数附近的性能变化 | 稳定性评分、敏感参数识别 |
| 样本外检验 | 固定训练期+测试期分离 | 样本内vs样本外性能对比 |
| 参数空间可视化 | 热力图展示参数-性能关系 | 参数稳定性热力图 |

### 3.3 API设计

```python
from eqlib.scientific.overfitting import (
    walk_forward_analysis,
    parameter_sensitivity,
    out_of_sample_test,
    OverfittingReport
)

# Walk-forward分析
wf_result = walk_forward_analysis(
    initialize_func=initialize,
    param_ranges=PARAM_RANGES,
    train_window='2Y',
    test_window='6M',
    step='6M',
    start_date='2020-01-01',
    end_date='2024-12-31'
)

# 参数敏感性
sensitivity = parameter_sensitivity(
    strategy_file='my_strategy.py',
    base_params=PARAMS,
    perturbation_pct=0.1
)

# 样本外检验
oos_result = out_of_sample_test(
    initialize_func=initialize,
    train_period=('2020-01-01', '2023-12-31'),
    test_period=('2024-01-01', '2024-12-31'),
    optimize_on_train=True
)
```

### 3.4 过拟合判定标准

```python
class OverfittingWarning:
    HIGH_OVERFITTING = "样本外Sharpe衰减 > 50%"
    MEDIUM_OVERFITTING = "样本外Sharpe衰减 30-50%"
    LOW_OVERFITTING = "样本外Sharpe衰减 < 30%"
    STABLE = "样本外Sharpe衰减 < 10%"
```

---

## 4. 统计置信度模块 (`statistics.py`)

### 4.1 目标

量化回测结果的统计可信度，判断结果是否可能由运气产生。

### 4.2 核心功能

| 功能 | 说明 | 适用场景 |
|-----|------|---------|
| Bootstrap检验 | 重采样计算Sharpe/收益置信区间 | 交易次数较少时 |
| 蒙特卡洛模拟 | 随机参数/随机时间窗口多次回测 | 评估参数稳定性 |
| 显著性检验 | t检验验证策略收益是否显著优于基准 | 与基准对比 |
| 样本量评估 | 计算所需最小交易次数/时间跨度 | 判断数据是否足够 |

### 4.3 API设计

```python
from eqlib.scientific.statistics import (
    bootstrap_metrics,
    monte_carlo_simulation,
    significance_test,
    sample_size_assessment,
    ConfidenceReport
)

# Bootstrap置信区间
bootstrap_result = bootstrap_metrics(
    backtest_result=result,
    n_bootstrap=1000,
    metrics=['sharpe_ratio', 'annual_return', 'max_drawdown']
)
# 输出: sharpe_ratio: 1.2 (95% CI: [0.8, 1.6])

# 蒙特卡洛模拟
mc_result = monte_carlo_simulation(
    initialize_func=initialize,
    n_simulations=500,
    random_start_dates=True,
    random_params=True,
    param_ranges=PARAM_RANGES
)

# 显著性检验
sig_result = significance_test(
    strategy_returns=result.daily_returns,
    benchmark_returns=index_returns,
    test_type='t-test'
)

# 样本量评估
sample_assess = sample_size_assessment(
    trade_count=45,
    time_span_years=3,
    target_sharpe=1.0
)
```

### 4.4 置信度判定标准

```python
class ConfidenceLevel:
    HIGH_CONFIDENCE = "95% CI宽度 < 30%均值, p < 0.05"
    MEDIUM_CONFIDENCE = "95% CI宽度 30-50%均值, p < 0.10"
    LOW_CONFIDENCE = "95% CI宽度 > 50%均值, p > 0.10"
    INSUFFICIENT_DATA = "交易次数 < 30 或 时间跨度 < 2年"
```

---

## 5. 偏差检测与处理模块 (`bias.py`)

### 5.1 目标

识别和标记回测中可能存在的各类偏差，提供修正建议。

### 5.2 核心功能

| 偏差类型 | 检测方法 | 处理方式 |
|---------|---------|---------|
| 幸存者偏差 | 检查股票池是否只包含当前存活股票 | 使用历史完整股票池（含退市股） |
| 前视偏差 | 检查是否使用了未来数据 | 标记可疑代码位置，建议修正 |
| 选择偏差 | 检查股票筛选条件是否过度过滤 | 计算筛选率，警告过度过滤 |
| 数据偏差 | 检查数据源缺失、异常值 | 标记缺失时段，建议填充策略 |

### 5.3 API设计

```python
from eqlib.scientific.bias import (
    check_survivorship_bias,
    check_lookahead_bias,
    check_selection_bias,
    check_data_bias,
    BiasReport,
    SurvivorshipCorrectedData
)

# 幸存者偏差检测
survivor_check = check_survivorship_bias(
    stock_pool=['000001.XSHE', '600000.XSHG', ...],
    start_date='2020-01-01',
    end_date='2024-12-31',
    data_source='akshare'
)

# 获取修正后数据
corrected_data = SurvivorshipCorrectedData(
    start_date='2020-01-01',
    end_date='2024-12-31'
)

# 前视偏差检测
lookahead_check = check_lookahead_bias(
    strategy_file='my_strategy.py',
    data_usage_log=result.data_access_log
)

# 选择偏差检测
selection_check = check_selection_bias(
    filter_conditions=['pe < 20', 'cap > 50e9', 'roe > 15'],
    universe='全A股',
    date='2024-01-01'
)

# 数据偏差检测
data_check = check_data_bias(
    backtest_result=result,
    data_source='akshare'
)
```

### 5.4 偏差严重程度分级

```python
class BiasSeverity:
    CRITICAL = "可能导致回测结果完全不可信，必须修正"
    HIGH = "可能影响10%+收益，建议修正"
    MEDIUM = "可能影响5-10%收益，建议核查"
    LOW = "影响较小，可记录备查"
    NONE = "未检测到明显偏差"
```

---

## 6. 扩展风险度量模块 (`risk.py`)

### 6.1 目标

提供超越Sharpe/最大回撤的专业级风险指标。

### 6.2 核心功能

| 指标 | 说明 | 专业用途 |
|-----|------|---------|
| Sortino比率 | 只惩罚下行波动 | 区分"好波动"和"坏波动" |
| Calmar比率 | 年收益/最大回撤 | 评估回撤容忍度 |
| VaR | 95%置信下最大单日损失 | 机构风控标准指标 |
| CVaR | VaR超出时的平均损失 | 评估尾部风险 |
| 下行风险 | 只计算负收益的波动率 | 更准确的风险度量 |
| 压力测试 | 极端市场情景模拟 | 评估策略在危机中的表现 |
| 尾部风险指标 | 峰度、偏度、最大连续亏损 | 识别黑天鹅暴露 |

### 6.3 API设计

```python
from eqlib.scientific.risk import (
    extended_risk_metrics,
    value_at_risk,
    conditional_var,
    stress_test,
    tail_risk_analysis,
    RiskReport
)

# 扩展风险指标
risk_metrics = extended_risk_metrics(
    backtest_result=result,
    benchmark_returns=index_returns
)

# VaR计算
var_result = value_at_risk(
    returns=result.daily_returns,
    confidence_level=0.95,
    method='historical'
)

# CVaR
cvar_result = conditional_var(
    returns=result.daily_returns,
    confidence_level=0.95
)

# 压力测试
stress_result = stress_test(
    backtest_result=result,
    scenarios=[
        {'name': '2008金融危机', 'shock': -0.40, 'duration': '6M'},
        {'name': '2015股灾', 'shock': -0.30, 'duration': '2M'},
        {'name': '2020疫情暴跌', 'shock': -0.15, 'duration': '1M'},
        {'name': '流动性危机', 'volume_drop': 0.5, 'spread_increase': 3}
    ]
)

# 尾部风险分析
tail_risk = tail_risk_analysis(
    returns=result.daily_returns
)
```

### 6.4 风险评级标准

```python
class RiskRating:
    LOW_RISK = "VaR < 3%, 最大回撤 < 15%, 尾部风险低"
    MEDIUM_RISK = "VaR 3-5%, 最大回撤 15-25%, 尾部风险中等"
    HIGH_RISK = "VaR > 5%, 最大回撤 > 25%, 尾部风险高"

    RESILIENT = "压力情景下损失 < 基准"
    VULNERABLE = "压力情景下损失 > 基准20%"
    CRITICAL = "压力情景下损失 > 基准50%"
```

---

## 7. 平台对比校验模块 (`comparison.py`)

### 7.1 目标

与专业平台（JoinQuant、聚宽等）对比，验证回测结果可信度。

### 7.2 核心功能

| 功能 | 说明 | 用途 |
|-----|------|------|
| 基准对齐检测 | 检查基准数据是否一致 | 排除基准差异导致的Alpha偏差 |
| 收益曲线对比 | 与平台收益曲线可视化对比 | 直观判断结果一致性 |
| 指标差异分析 | 对比关键指标差异并解释 | 识别差异来源 |
| 交易记录核对 | 对比交易时点/价格 | 验证执行逻辑是否正确 |

### 7.3 API设计

```python
from eqlib.scientific.comparison import (
    align_benchmark,
    compare_with_platform,
    compare_metrics,
    verify_trades,
    ComparisonReport
)

# 基准对齐
benchmark_align = align_benchmark(
    local_benchmark='沪深300',
    platform_benchmark='JoinQuant沪深300',
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# 平台对比
comparison = compare_with_platform(
    local_result=result,
    platform_result=joinquant_export,
    platform_name='JoinQuant'
)

# 交易记录核对
trade_verify = verify_trades(
    local_trades=result.trades,
    platform_trades=joinquant_trades,
    price_tolerance=0.01
)
```

### 7.4 对比判定标准

```python
class ComparisonJudgment:
    RESULT_ALIGNED = "关键指标差异 < 5%，结果可信"
    RESULT_ACCEPTABLE = "关键指标差异 5-15%，可能为设置差异"
    RESULT_SUSPICIOUS = "关键指标差异 > 15%，建议核查"
    RESULT_MISMATCHED = "交易记录不一致，可能存在逻辑问题"
```

---

## 8. 统一验证流程编排 (`validation_runner.py`)

### 8.1 目标

一键运行完整科学验证流程，避免用户手动调用多个模块。

### 8.2 核心功能

| 功能 | 说明 |
|-----|------|
| 验证流程编排 | 按预设顺序运行所有验证模块 |
| 参数配置 | 统一配置入口，控制启用哪些验证 |
| 结果汇总 | 整合所有模块结果为统一报告 |
| 计算资源管理 | 控制并行度、估算耗时 |

### 8.3 API设计

```python
from eqlib.scientific import validate_backtest, ValidationConfig

config = ValidationConfig(
    overfitting=True,
    walk_forward_windows={'train': '2Y', 'test': '6M', 'step': '6M'},
    parameter_sensitivity=True,

    statistics=True,
    n_bootstrap=1000,
    n_monte_carlo=500,
    significance_level=0.05,

    bias_check=True,
    check_survivorship=True,
    check_lookahead=True,

    risk_metrics='extended',
    stress_test_scenarios='default',

    comparison=False,

    parallel_workers=4,
    timeout_minutes=30
)

validation_result = validate_backtest(
    backtest_result=result,
    config=config,
    strategy_file='my_strategy.py'
)

validation_result.summary()
validation_result.save_report('validation_report.html')
```

### 8.4 验证流程执行顺序

```
1. 偏差检测 → 先排除基础问题，若CRITICAL则终止后续验证
2. 风险度量 → 基础指标计算
3. 统计置信度 → Bootstrap/Monte Carlo（较耗时）
4. 过拟合检测 → Walk-forward（最耗时）
5. 平台对比 → 需外部数据时执行
6. 报告生成 → 汇总所有结果
```

### 8.5 总体信任度评级

```python
class TrustRating:
    HIGH_TRUST = "所有验证通过，可用于实盘决策"
    MEDIUM_TRUST = "部分警告，建议核查后使用"
    LOW_TRUST = "存在重大问题，不建议实盘使用"
    INSUFFICIENT_DATA = "数据不足，无法建立信任"
```

---

## 9. 科学验证报告生成 (`report.py`)

### 9.1 目标

生成专业级可视化报告，清晰呈现验证结果。

### 9.2 输出格式

| 格式 | 说明 | 用途 |
|-----|------|------|
| HTML | 交互式网页报告，含图表 | 详细审阅、分享 |
| Markdown | 文本格式报告 | 文档集成、Git提交 |
| JSON | 结构化数据 | 程序读取、自动化流程 |
| PNG | 关键可视化图表 | 快速分享、嵌入PPT |

### 9.3 报告内容结构

```
验证报告结构：
├── 1. 执行摘要
│   ├── 总体信任度评级
│   ├── 关键发现（3条）
│   └── 建议行动
│
├── 2. 过拟合分析
│   ├── Walk-forward性能趋势图
│   ├── 参数敏感性热力图
│   ├── 样本内vs样本外对比表
│   └── 过拟合评级
│
├── 3. 统计置信度
│   ├── Bootstrap置信区间表
│   ├── Monte Carlo Sharpe分布图
│   ├── 显著性检验结果
│   └── 置信度评级
│
├── 4. 偏差检测结果
│   ├── 各偏差检测状态表
│   ├── 警告详情列表
│   └── 修正建议
│
├── 5. 风险度量
│   ├── 扩展风险指标表
│   ├── VaR/CVaR可视化
│   ├── 压力测试情景对比图
│   ├── 尾部风险分析
│   └── 风险评级
│
├── 6. 平台对比（若启用）
│   ├── 指标对比表
│   ├── 收益曲线对比图
│   └── 差异分析
│
└── 7. 附录
    ├── 验证配置参数
    ├── 方法说明
    ├── 数据来源说明
```

### 9.4 API设计

```python
from eqlib.scientific.report import (
    generate_validation_report,
    ValidationReport,
    ReportConfig
)

report = generate_validation_report(
    validation_result,
    config=ReportConfig(
        format=['html', 'markdown', 'json'],
        include_charts=True,
        charts_format='png',
        language='zh',
        output_dir='./validation_reports/'
    )
)
```

### 9.5 可视化图表

- `walk_forward_performance_trend` — 各窗口Sharpe/收益趋势线
- `parameter_sensitivity_heatmap` — 参数扰动-性能热力图
- `train_test_comparison` — 训练期vs测试期对比柱状图
- `bootstrap_confidence_interval` — Bootstrap CI误差棒图
- `monte_carlo_sharpe_distribution` — Monte Carlo Sharpe分布直方图
- `var_cvar_comparison` — VaR/CVaR对比
- `stress_test_scenarios` — 各压力情景损失对比
- `return_distribution` — 收益分布+尾部标注
- `return_curve_comparison` — EasyQuant vs 平台收益曲线

---

## 10. Web Strategy Studio集成

### 10.1 后端新增路由

```python
# web_strategy_studio/backend/studio_api/routers/validation.py

@router.post("/api/strategies/{strategy_id}/validate")
async def validate_strategy(
    strategy_id: int,
    config: ValidationConfigAPI,
    db: AsyncSession = Depends(get_db)
):
    """运行科学验证流程"""

@router.get("/api/strategies/{strategy_id}/validation/{run_id}")
async def get_validation_result(run_id: int):
    """获取验证结果详情"""

@router.get("/api/strategies/{strategy_id}/validation/{run_id}/report")
async def download_validation_report(run_id: int, format: str = 'html'):
    """下载验证报告"""
```

### 10.2 前端新增组件

```
frontend/src/
├── pages/
│   └── ValidationPage.tsx
├── components/
│   ├── ValidationConfigPanel.tsx
│   ├── ValidationSummaryCard.tsx
│   ├── OverfittingChart.tsx
│   ├── ConfidenceIntervalChart.tsx
│   ├── RiskMetricsTable.tsx
│   ├── BiasWarningsList.tsx
├── api/
│   └── validation.ts
```

### 10.3 数据库扩展

```python
class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: int
    strategy_id: int
    backtest_run_id: int
    trust_rating: str
    overfitting_level: str
    confidence_level: str
    bias_severity: str
    risk_rating: str
    validation_details: JSON
    report_html_path: str
    report_json_path: str
    created_at: datetime
```

---

## 11. 错误处理策略

| 错误类型 | 处理方式 |
|---------|---------|
| 计算超时 | 返回部分结果+超时警告，建议减少模拟次数 |
| 数据缺失 | 偏差检测模块标记，不中断验证流程 |
| 参数无效 | 配置验证时检查，返回明确错误信息 |
| 资源不足 | 检测可用内存/CPU，建议降低并行度 |
| 平台数据格式错误 | 提示用户检查导入格式，提供格式模板 |

```python
class ValidationError(Exception):
    INSUFFICIENT_DATA = "数据不足，无法执行验证"
    COMPUTATION_TIMEOUT = "计算超时"
    INVALID_CONFIG = "配置参数无效"
    RESOURCE_LIMIT = "计算资源不足"
```

---

## 12. 测试策略

### 12.1 单元测试

```
tests/scientific/
├── test_overfitting.py
├── test_statistics.py
├── test_bias.py
├── test_risk.py
├── test_comparison.py
├── test_validation_runner.py
├── test_report.py
```

### 12.2 集成测试

```
tests/integration/
├── test_full_validation_flow.py
├── test_web_validation_api.py
├── test_validation_with_real_strategy.py
```

### 12.3 测试数据准备

- 已知结果的测试策略（过拟合/正常/高风险）
- 模拟的平台对比数据
- 含偏差的测试数据集（幸存者偏差样本）

---

## 13. 实施计划概要

**预计周期**: 1-2个月

| 阶段 | 内容 | 时间 |
|-----|------|------|
| 第1周 | 架构搭建 + 偏差检测模块 | 基础框架 |
| 第2-3周 | 统计置信度模块 + 风险度量模块 | 核心计算 |
| 第4周 | 过拟合检测模块 | 复杂验证 |
| 第5周 | 平台对比模块 + 验证流程编排 | 集成层 |
| 第6周 | 报告生成 + Web集成 | 用户界面 |
| 第7-8周 | 测试 + 文档 + 优化迭代 | 质量保障 |

---

## 14. 计算资源需求

| 功能 | 资源需求 | 建议 |
|-----|---------|------|
| Bootstrap (n=1000) | 中等 | 本地机器可完成 |
| Monte Carlo (n=500) | 较高 | 可并行加速 |
| Walk-forward分析 | 高 | 长时间跨度需云服务器 |
| 压力测试 | 低 | 本地即可 |

**建议**: 默认配置面向本地机器，高负载场景提供云服务器选项。

---

## 15. 后续阶段关联

Phase 1 为后续阶段奠定基础：

- **Phase 2 (专业级分析报告)** — 使用 Phase 1 的风险指标和归因模块
- **Phase 3 (策略广度与深度)** — 使用 Phase 1 的验证流程检验新策略
- **Phase 4 (实盘交易能力)** — 使用 Phase 1 的信任评级决定是否上线

---

**文档状态**: 已确认，待用户审阅后进入实施计划阶段