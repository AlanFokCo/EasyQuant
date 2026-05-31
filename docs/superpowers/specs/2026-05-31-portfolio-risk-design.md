# 组合级风控模块设计规格

> 创建时间：2026-05-31
> 状态：设计完成，待实现

---

## 一、概述

### 背景

EasyQuant 已有完善的策略验证体系（`eqlib/scientific/`），但缺失**组合级风控**能力。A股系统性风险高（政策风险、流动性危机），单策略风控不够，需要多策略组合的风险监控。

### 目标

实现 `eqlib/portfolio_risk.py` 模块，提供：
- 组合 VaR（风险价值）
- 策略相关性矩阵
- 集中度风险监控
- 市场 regime 检测
- 三级预警与熔断机制

### 优先级

P0（极高）— A股系统性风险高，组合风控是生存底线。

---

## 二、架构

### 模块结构

```
eqlib/portfolio_risk.py（单文件模块）
├── AlertLevel (枚举: YELLOW/RED/KILL_SWITCH)
├── RiskThresholds (阈值配置类)
├── RiskReport (风控报告类)
├── PortfolioRiskMonitor (主类)
│   ├── add_strategy()
│   ├── portfolio_var()
│   ├── correlation_matrix()
│   ├── concentration_risk()
│   ├── regime_detection()
│   └── daily_check()
└── check_kill_switch() (独立熔断函数)
```

### 集成方式

渐进式集成：
- **阶段一**：独立模块，用户手动调用
- **阶段二**：集成到 `run_backtest()`，可选自动风控检查
- **阶段三**：集成到 `run_paper_trade()`，实盘自动预警
- **阶段四**：Web Studio 前端仪表盘（后续）

---

## 三、核心类与数据结构

### AlertLevel 预警级别

```python
class AlertLevel(Enum):
    """预警级别"""
    YELLOW = "yellow"      # 监控关注，不触发动作
    RED = "red"            # 需要人工介入
    KILL_SWITCH = "kill"   # 自动熔断 + 人工确认
```

### RiskThresholds 阈值配置

```python
@dataclass
class RiskThresholds:
    """风控阈值配置"""
    # 回撤阈值
    max_drawdown_yellow: float = 0.15   # 黄色预警回撤
    max_drawdown_red: float = 0.20      # 红色预警回撤
    max_drawdown_kill: float = 0.25     # 熔断回撤
    
    # 相关性阈值
    correlation_yellow: float = 0.60    # 黄色预警相关性
    correlation_red: float = 0.75       # 红色预警相关性
    correlation_kill: float = 0.85      # 熔断相关性
    
    # 集中度阈值
    single_stock_max: float = 0.10      # 单股票最大占比
    single_sector_max: float = 0.30     # 单板块最大占比
    small_cap_max: float = 0.20         # 微盘股最大占比（<50亿）
    
    # VaR 置信水平
    var_confidence: float = 0.95
```

用户可通过构造函数覆盖默认值。

### RiskReport 风控报告

```python
@dataclass
class RiskReport:
    """风控检查报告"""
    timestamp: pd.Timestamp
    alert_level: AlertLevel
    triggers: List[str]              # 触发的预警信息列表
    portfolio_var: Optional[float]   # 组合 VaR（金额）
    portfolio_var_pct: Optional[float] # 组合 VaR（百分比）
    correlation_matrix: Optional[pd.DataFrame]  # 策略相关性矩阵
    concentration: Optional[Dict[str, float]]   # 集中度指标
    regime: Optional[str]            # 当前市场 regime
    recommendations: List[str]       # 建议操作
```

---

## 四、PortfolioRiskMonitor 主类

### 初始化

```python
class PortfolioRiskMonitor:
    def __init__(self, thresholds: Optional[RiskThresholds] = None):
        self.thresholds = thresholds or RiskThresholds()
        self._strategy_results: Dict[str, Any] = {}  # 存储各策略回测结果
```

### add_strategy() 添加策略

```python
def add_strategy(self, name: str, backtest_result: Dict) -> None:
    """添加策略回测结果
    
    Parameters:
        name: 策略名称（如 "均线策略"、"因子策略"）
        backtest_result: run_backtest() 返回的 result dict
        
    Raises:
        ValueError: 回测结果为空或缺少 recorded_values
    """
```

### portfolio_var() 组合 VaR

**算法**：历史模拟法

**流程**：
1. 从各策略 `recorded_values` 提取日收益率序列
2. 拼接为组合日收益率（按资产权重加权）
3. 取历史分布的 confidence 分位数（如 95% 分位数）
4. 转换为金额和百分比

**返回**：`(var_amount, var_pct)`

### correlation_matrix() 策略相关性

**算法**：Pearson 相关系数

**流程**：
1. 从各策略提取日收益率序列
2. 计算策略间 Pearson 相关性
3. 返回 DataFrame（行列均为策略名称）

**用途**：高相关性策略需要减仓（分散化失效预警）

### concentration_risk() 集中度风险

**流程**：
1. 遍历所有策略的当前持仓
2. 获取股票市值、所属板块（通过 akshare）
3. 计算各维度集中度

**返回**：
```python
{
    'max_single_stock': 单股票最大持仓占比,
    'max_single_sector': 单板块最大持仓占比,
    'small_cap_pct': 微盘股占比（市值<50亿）,
    'num_holdings': 持仓股票数量,
    'top3_concentration': 前三大持仓占比
}
```

### regime_detection() 市场 Regime

**算法**：简单趋势法（沪深300均线）

**流程**：
1. 获取沪深300 近60日收盘价
2. 计算 MA20 和 MA60
3. 判断：
   - MA20 > MA60 且间距 > 2% → `bull`
   - MA20 < MA60 且间距 > 2% → `bear`
   - 其他 → `oscillation`

**返回**：`'bull'` / `'bear'` / `'oscillation'`

### daily_check() 综合检查

**主入口方法，一键获取完整风控报告**

**流程**：
1. 计算 `portfolio_var()`
2. 计算 `correlation_matrix()`
3. 计算 `concentration_risk()`
4. 执行 `regime_detection()`
5. 对照阈值，判断预警级别
6. 生成触发信息和建议操作
7. 返回完整 `RiskReport`

**预警级别确定**：
- 有"熔断"触发 → `KILL_SWITCH`
- 有"红色"触发 → `RED`
- 其他 → `YELLOW`

---

## 五、熔断逻辑

### check_kill_switch() 独立函数

```python
def check_kill_switch(report: RiskReport) -> List[str]:
    """熔断检查
    
    Returns:
        需要立即执行的熔断操作列表
        
        如: ["暂停策略: 均线策略", "清仓股票: 601390"]
    """
```

**触发条件**：
- 回撤超过熔断阈值 → 暂停所有策略，等待人工确认
- 相关性超过熔断阈值 → 降低高相关性策略仓位 50%
- 集中度超过阈值 → 建议减仓超标股票

---

## 六、错误处理

| 边界情况 | 处理方式 |
|---------|---------|
| 无策略数据 | `portfolio_var()` 返回 (0, 0)，其他方法返回空结构 |
| 单策略 | 相关性矩阵返回空 DataFrame，触发信息标注"需添加更多策略" |
| 数据天数不足（<30天） | VaR 返回 NaN，触发信息标注"数据不足，无法计算" |
| 市值/板块数据获取失败 | 使用保守估计或跳过该项检查，不中断流程 |
| akshare API 异常 | 捕获异常，返回默认值，触发信息标注"数据获取失败" |

**原则**：优雅降级，不中断流程，标注数据问题。

---

## 七、使用示例

```python
from eqlib import run_backtest
from eqlib.portfolio_risk import PortfolioRiskMonitor, check_kill_switch, AlertLevel

# 1. 运行多个策略回测
result_ma = run_backtest(ma_initialize, start_date='2024-01-01', end_date='2024-12-31')
result_factor = run_backtest(factor_initialize, start_date='2024-01-01', end_date='2024-12-31')

# 2. 创建风控监控器
monitor = PortfolioRiskMonitor()

# 3. 添加策略
monitor.add_strategy("均线策略", result_ma)
monitor.add_strategy("因子策略", result_factor)

# 4. 综合检查
report = monitor.daily_check()

# 5. 查看结果
print(f"预警级别: {report.alert_level.value}")
print(f"组合 VaR: ¥{report.portfolio_var:,.2f} ({report.portfolio_var_pct:.2%})")
print(f"市场 regime: {report.regime}")
print("触发预警:")
for t in report.triggers:
    print(f"  - {t}")

# 6. 熔断检查
if report.alert_level in [AlertLevel.RED, AlertLevel.KILL_SWITCH]:
    actions = check_kill_switch(report)
    for action in actions:
        print(f"⚠️ 建议操作: {action}")

# === 自定义阈值 ===

from eqlib.portfolio_risk import RiskThresholds

custom_thresholds = RiskThresholds(
    max_drawdown_kill=0.15,  # 更严格的熔断阈值
    single_stock_max=0.08,   # 更严格的单股票限制
    correlation_red=0.65,    # 更敏感的相关性预警
)
monitor = PortfolioRiskMonitor(thresholds=custom_thresholds)
```

---

## 八、导出配置

`eqlib/__init__.py` 需添加：

```python
from eqlib.portfolio_risk import (
    PortfolioRiskMonitor,
    RiskThresholds,
    RiskReport,
    AlertLevel,
    check_kill_switch,
)
```

---

## 九、测试策略

### 单元测试

- `test_portfolio_var()`：验证 VaR 计算准确性
- `test_correlation_matrix()`：验证相关性计算
- `test_concentration_risk()`：验证集中度计算
- `test_regime_detection()`：验证 regime 判断

### 集成测试

- `test_daily_check()`：模拟完整检查流程
- `test_multi_strategy()`：多策略组合测试

### 边界测试

- `test_no_strategy()`：无策略数据
- `test_single_strategy()`：单策略
- `test_insufficient_data()`：数据不足
- `test_api_failure()`：akshare API 异常模拟

### 回测验证

用真实回测数据测试，确保结果符合预期。

---

## 十、验收标准

1. 能计算多策略组合 VaR（历史模拟法）
2. 能生成策略相关性矩阵
3. 能计算集中度风险（单股票、板块、微盘股）
4. 能检测市场 regime（牛市/熊市/震荡）
5. 能生成三级预警报告
6. 能触发熔断建议
7. 单元测试覆盖率 > 80%
8. 与现有 `run_backtest()` API 无缝衔接

---

## 十一、后续扩展

- 集成到 `run_backtest()`（可选每日风控检查）
- 集成到 `run_paper_trade()`（实盘自动预警通知）
- Web Studio 前端风控仪表盘
- 多指标综合 regime 检测（北向资金、涨跌停）
- Monte Carlo VaR 作为可选深度分析