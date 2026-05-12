"""EasyQuant AI Agent — strategy optimization support utilities.

Modules:
    audit_log         — structured audit logging (JSONL + Markdown), used directly by Claude Code
    optimizer         — reference rule-based optimizer (optional, for comparison)
    strategy_template — parameterized strategy template for AI-driven optimization

The primary AI-driven optimization workflow is orchestrated by Claude Code itself,
which reads strategy files, runs backtests via eqlib APIs, analyzes results, edits
strategy files, spawns code-review sub-agents, and writes audit logs. The optimizer
module is a standalone reference utility, not the primary driver.
"""
