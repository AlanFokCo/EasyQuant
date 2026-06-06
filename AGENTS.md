# Repository Guidelines

This guide helps contributors work effectively with the EasyQuant codebase.

## Project Structure

- **Core library**: `eqlib/` — Event-driven backtesting engine for China A-share market
- **Tests**: `tests/` — pytest suite with smoke tests for examples
- **Examples**: `examples/` — Numbered tutorials (01-20) demonstrating library features
- **Documentation**: `docs/` — MkDocs site with bilingual support (Chinese + `.en.md` English)
- **Web Studio**: `web_strategy_studio/` — FastAPI backend + React frontend
- **Scripts**: `scripts/` — Validation utilities like `check_doc_sync.py`

## Build & Test Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run all tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_imports.py -v

# Run example smoke test
python examples/03_run_backtest.py

# Build docs locally
mkdocs serve
```

## Coding Style

- **Python**: Use type hints, keep imports explicit (avoid `from eqlib import *` in examples)
- **Linting**: Pre-commit hooks enforce trailing whitespace, EOF fixes, YAML/TOML validation
- **Backend code**: ruff (lint + import sort), black (format), mypy (type check)
- **API stability**: Mark exports in `eqlib/__init__.py` as `STABLE`, `EXPERIMENTAL`, or `DEPRECATED`
- **Constants**: Use `eqlib/constants.py` for `RISK_FREE_RATE` (0.03) and `TRADING_DAYS_PER_YEAR` (244)

## Testing Guidelines

- **Framework**: pytest 7.0+ with coverage via pytest-cov
- **Naming**: Files as `test_*.py`, functions as `test_*()`
- **Smoke tests**: `tests/test_examples_smoke.py` validates all examples run without error
- **Coverage**: Focus on `eqlib/` core logic; examples serve as integration tests

## Commit & Pull Request Guidelines

**Commit prefixes**:
- `docs:` — Documentation (always update both `.md` and `.en.md`)
- `fix:` — Bug fixes
- `feat:` — New features or examples
- `chore:` — Cleanup, reorganization
- `refactor:` — Code restructuring without behavior change

**Pull request requirements**:
- Update both Chinese and English docs when modifying `docs/**/*.md`
- Run `python scripts/check_doc_sync.py` before committing
- Ensure examples pass smoke tests
- Update `examples/README.md` and `docs/examples/index.md` when adding/renaming examples

## Agent-Specific Instructions

When modifying examples:
1. Use `examples/_defaults.py` for trading costs and stock codes
2. Include module docstring with number, title, description, and teaching objectives
3. Add `if __name__ == "__main__":` guard
4. Update both example indices after changes

When changing public APIs in `eqlib/`:
1. Update all affected examples
2. Update tutorial docs (both languages)
3. Update `docs/reference/` API docs
4. Run full test suite + smoke tests
5. Build docs with `mkdocs build --strict`

Trading costs must match `examples/_defaults.py`: stamp duty 0.05%, commission 0.025%, minimum 5 CNY.
