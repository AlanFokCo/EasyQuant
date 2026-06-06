"""Template service for strategy templates.

Loads built-in strategy templates from a JSON file and provides them
via a clean API. Templates are used to quickly bootstrap new strategies
with common patterns (double MA, momentum, mean reversion, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional


class TemplateService:
    """Service for managing strategy templates."""

    def __init__(self, templates_file: Optional[Path] = None):
        if templates_file is None:
            templates_file = (
                Path(__file__).parent.parent / "data" / "templates.json"
            )
        self.templates_file = templates_file
        self._templates: Dict[str, dict] = self._load_templates()

    def _load_templates(self) -> Dict[str, dict]:
        """Load templates from file, falling back to defaults if file missing."""
        if self.templates_file.exists():
            try:
                data = json.loads(self.templates_file.read_text(encoding="utf-8"))
                # Validate structure: each entry needs name, description, code
                templates = {}
                for tid, entry in data.items():
                    if isinstance(entry, dict) and "code" in entry:
                        templates[tid] = {
                            "id": tid,
                            "name": entry.get("name", tid),
                            "description": entry.get("description", ""),
                            "code": entry["code"],
                            "category": entry.get("category", "general"),
                            "tags": entry.get("tags", []),
                        }
                return templates
            except (json.JSONDecodeError, OSError):
                pass
        return self._default_templates()

    def _default_templates(self) -> Dict[str, dict]:
        """Fallback templates when JSON file is missing or corrupt."""
        return {
            "double_ma": {
                "id": "double_ma",
                "name": "双均线策略",
                "description": "基于5日和20日均线的简单交叉策略",
                "code": (
                    '"""双均线策略 — 金叉买入，死叉卖出."""\n'
                    "from eqlib import *\n\n\n"
                    "def initialize(context):\n"
                    '    g.security = "601390"\n'
                    "    g.fast_period = 5\n"
                    "    g.slow_period = 20\n"
                    '    set_benchmark("000300.XSHG")\n'
                    "    context.universe = [g.security]\n"
                    '    run_daily(market_open, time="every_bar")\n\n\n'
                    "def market_open(context):\n"
                    "    security = g.security\n"
                    '    close_data = attribute_history(security, 25, "1d", ["close"])\n'
                    "    if close_data.empty or len(close_data) < g.slow_period:\n"
                    "        return\n"
                    '    fast_ma = close_data["close"].tail(g.fast_period).mean()\n'
                    '    slow_ma = close_data["close"].tail(g.slow_period).mean()\n'
                    "    prev_fast = close_data['close'].tail(g.fast_period + 1).head(g.fast_period).mean()\n"
                    "    prev_slow = close_data['close'].tail(g.slow_period + 1).head(g.slow_period).mean()\n"
                    "    if prev_fast <= prev_slow and fast_ma > slow_ma:\n"
                    "        order_value(security, context.portfolio.available_cash)\n"
                    "    elif prev_fast >= prev_slow and fast_ma < slow_ma:\n"
                    "        order_target(security, 0)\n"
                ),
                "category": "trend",
                "tags": ["均线", "趋势", "入门"],
            },
        }

    def get_templates(self) -> List[dict]:
        """Get all available templates (summary only — no code).

        Returns:
            List of template metadata dicts (id, name, description, category, tags).
        """
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "description": t["description"],
                "category": t.get("category", "general"),
                "tags": t.get("tags", []),
            }
            for t in self._templates.values()
        ]

    def get_template(self, template_id: str) -> Optional[dict]:
        """Get a specific template with full code.

        Args:
            template_id: Template identifier.

        Returns:
            Full template dict or None if not found.
        """
        t = self._templates.get(template_id)
        if t is None:
            return None
        return {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "code": t["code"],
            "category": t.get("category", "general"),
            "tags": t.get("tags", []),
        }
