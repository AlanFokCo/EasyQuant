"""EasyQuant strategy optimization support utilities.

Modules:
    audit_log         — structured audit logging (JSONL + Markdown)
    optimizer         — reference rule-based parameter search (CLI / library)
    strategy_template — parameterized strategy template for tuning workflows

Use ``optimizer.py`` for a reproducible rule-based baseline. Use ``audit_log.py`` from
your own scripts or notebooks when you want JSONL + Markdown traces. Neither module
depends on a specific IDE or vendor AI product.
"""
