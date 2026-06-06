"""Run examples and capture their metrics."""
import os
import re
import subprocess
import json

examples = [
    ("15_bollinger_strategy.py", "Bollinger"),
    ("16_macd_volume.py", "MACD"),
    ("18_grid_trading.py", "Grid"),
    ("17_multi_factor.py", "MultiFactor"),
    ("10_index_concept.py", "StockSelection"),
    ("11_portfolio_backtest.py", "Portfolio"),
]

results = {}

for script, name in examples:
    print(f"\n=== Running {name}: {script} ===")
    result = subprocess.run(
        ["python", f"examples/{script}"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "/Users/alanfok/EasyQuant"},
        timeout=300
    )
    
    output = result.stdout + result.stderr
    
    # Try to extract metrics from output
    metrics = {}
    
    # Total Return
    match = re.search(r'Total Return:\s*([\-+]?[0-9]+\.?[0-9]*)%', output)
    if match:
        metrics['total_return'] = match.group(1)
    
    # Annual Return
    match = re.search(r'Annual Return:\s*([\-+]?[0-9]+\.?[0-9]*)%', output)
    if match:
        metrics['annual_return'] = match.group(1)
    
    # Sharpe Ratio
    match = re.search(r'Sharpe Ratio:\s*([\-+]?[0-9]+\.?[0-9]*)', output)
    if match:
        metrics['sharpe'] = match.group(1)
    
    # Max Drawdown
    match = re.search(r'Max Drawdown:\s*([\-+]?[0-9]+\.?[0-9]*)%', output)
    if match:
        metrics['max_drawdown'] = match.group(1)
    
    # Trade Count
    match = re.search(r'Trade Count:\s*(\d+)', output)
    if match:
        metrics['trade_count'] = match.group(1)
    
    # Win Rate
    match = re.search(r'Win Rate:\s*([0-9]+\.?[0-9]*)%', output)
    if match:
        metrics['win_rate'] = match.group(1)
    
    results[name] = metrics
    print(f"  Metrics: {metrics}")

print("\n\n=== Summary ===")
for name, metrics in results.items():
    print(f"{name}: {metrics}")
