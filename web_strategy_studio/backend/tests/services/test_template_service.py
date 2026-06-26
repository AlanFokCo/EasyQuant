"""Tests for TemplateService — strategy template management.

Tests cover JSON loading, fallback defaults, and template retrieval.
All tests are synchronous (TemplateService is not async).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio_api.services.template_service import TemplateService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def svc() -> TemplateService:
    """Service using the real templates.json file."""
    return TemplateService()


@pytest.fixture
def custom_templates_file(tmp_path: Path) -> Path:
    """Create a temporary templates.json with known content."""
    templates = {
        "test_ma": {
            "name": "Test MA",
            "description": "A test template",
            "code": "def initialize(ctx):\n    pass\n",
            "category": "test",
            "tags": ["test"],
        },
        "test_momentum": {
            "name": "Test Momentum",
            "description": "Another test",
            "code": "def initialize(ctx):\n    g.x = 1\n",
            "category": "test",
            "tags": ["test", "momentum"],
        },
    }
    f = tmp_path / "templates.json"
    f.write_text(json.dumps(templates), encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------


class TestTemplateLoading:
    def test_loads_default_templates(self):
        """Service loads built-in templates when no file specified."""
        svc = TemplateService()
        templates = svc.get_templates()
        assert len(templates) >= 3, "Should have at least 3 built-in templates"

    def test_loads_from_custom_file(self, custom_templates_file):
        svc = TemplateService(templates_file=custom_templates_file)
        templates = svc.get_templates()
        assert len(templates) == 2

    def test_fallback_on_missing_file(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        svc = TemplateService(templates_file=missing)
        templates = svc.get_templates()
        assert len(templates) >= 1, "Should fall back to default templates"

    def test_fallback_on_corrupt_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json!!!", encoding="utf-8")
        svc = TemplateService(templates_file=bad_file)
        templates = svc.get_templates()
        assert len(templates) >= 1, "Should fall back to defaults on corrupt JSON"

    def test_skips_entries_without_code(self, tmp_path):
        """Templates without 'code' field should be silently skipped."""
        templates = {
            "good": {"name": "Good", "code": "pass"},
            "bad": {"name": "Bad", "description": "No code field"},
        }
        f = tmp_path / "templates.json"
        f.write_text(json.dumps(templates), encoding="utf-8")
        svc = TemplateService(templates_file=f)
        result = svc.get_templates()
        assert len(result) == 1
        assert result[0]["id"] == "good"


# ---------------------------------------------------------------------------
# get_templates (summary)
# ---------------------------------------------------------------------------


class TestGetTemplates:
    def test_returns_list(self, svc):
        templates = svc.get_templates()
        assert isinstance(templates, list)

    def test_each_has_required_fields(self, svc):
        templates = svc.get_templates()
        for t in templates:
            assert "id" in t
            assert "name" in t
            assert "description" in t
            assert "category" in t
            assert "tags" in t

    def test_does_not_include_code(self, svc):
        """Summary listing should not include code to save bandwidth."""
        templates = svc.get_templates()
        for t in templates:
            assert "code" not in t

    def test_builtin_categories(self, svc):
        templates = svc.get_templates()
        categories = {t["category"] for t in templates}
        assert "trend" in categories


# ---------------------------------------------------------------------------
# get_template (detail)
# ---------------------------------------------------------------------------


class TestGetTemplate:
    def test_returns_template_with_code(self, svc):
        template = svc.get_template("double_ma")
        assert template is not None
        assert "code" in template
        assert "def initialize" in template["code"]

    def test_returns_none_for_missing(self, svc):
        template = svc.get_template("nonexistent_template_xyz")
        assert template is None

    def test_double_ma_template(self, svc):
        template = svc.get_template("double_ma")
        assert template is not None
        assert template["name"] == "双均线策略"
        assert "eqlib" in template["code"]
        assert "initialize" in template["code"]

    def test_momentum_template(self, svc):
        template = svc.get_template("momentum")
        assert template is not None
        assert template["name"] == "动量策略"
        assert "initialize" in template["code"]

    def test_mean_reversion_template(self, svc):
        template = svc.get_template("mean_reversion")
        assert template is not None
        assert template["name"] == "均值回归策略"
        assert "initialize" in template["code"]

    def test_custom_file_template(self, custom_templates_file):
        svc = TemplateService(templates_file=custom_templates_file)
        t = svc.get_template("test_ma")
        assert t is not None
        assert t["name"] == "Test MA"
        assert t["code"] == "def initialize(ctx):\n    pass\n"
        assert t["tags"] == ["test"]


# ---------------------------------------------------------------------------
# Template code quality
# ---------------------------------------------------------------------------


class TestTemplateCodeQuality:
    def test_all_templates_have_valid_python(self, svc):
        """Every template's code should be valid Python."""
        import ast

        for t in svc.get_templates():
            full = svc.get_template(t["id"])
            try:
                ast.parse(full["code"])
            except SyntaxError as e:
                pytest.fail(f"Template '{t['id']}' has syntax error: {e}")

    def test_all_templates_have_initialize(self, svc):
        """Every template should define an initialize() function."""
        for t in svc.get_templates():
            full = svc.get_template(t["id"])
            assert "def initialize" in full["code"], f"Template '{t['id']}' missing initialize()"
