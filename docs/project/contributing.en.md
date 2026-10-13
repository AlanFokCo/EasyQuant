# Contributing to EasyQuant

Thanks for your interest in contributing to EasyQuant. We welcome bug reports, feature requests, documentation improvements, and code.

## How to Contribute

### Report Bugs

Use GitHub Issues to report bugs. Please include:

- A clear description of the bug
- Steps to reproduce (minimal example if possible)
- Expected vs. actual behavior
- Python version and `eqlib` version
- Relevant log output or error messages

### Suggest Features

Open a GitHub Issue to discuss new features before submitting a PR. This helps us align on scope and design.

### Submit Pull Requests

1. Fork the repo and create a feature branch (`git checkout -b feature/my-feature`)
2. Make your changes — follow the existing code style
3. Add or update tests in `tests/` for any code changes
4. Run the test suite: `python -m pytest tests/`
5. Commit with a conventional prefix (see below)
6. Push and open a PR against `main`

## Development Setup

```bash
pip install -e ".[dev]"
python -m pytest tests/
```

## Code Style

- Follow PEP 8 conventions; use type hints
- Keep imports explicit — avoid `from eqlib import *` in examples
- Add docstrings for public API functions
- Mark exports in `eqlib/__init__.py` as `STABLE`, `EXPERIMENTAL`, or `DEPRECATED`
- Use the shared constants in `eqlib/constants.py` (`RISK_FREE_RATE = 0.03`, `TRADING_DAYS_PER_YEAR = 244`) instead of hardcoding
- Pre-commit hooks enforce trailing whitespace, EOF fixes, and YAML/TOML validation

## Documentation

The docs live in `docs/` and are bilingual: every `*.md` file has an English `*.en.md` sibling.

- When you edit `docs/**/*.md`, update the matching `.en.md` in the same PR
- Run `python scripts/check_doc_sync.py` before committing — it checks translation pairing, stale example references, and that trading-cost figures match `examples/_defaults.py`
- CI runs `mkdocs build --strict`; you can verify locally with `mkdocs serve`
- Public API changes in `eqlib/` require updating affected examples, the tutorial docs (both languages), and `docs/reference/`

## Examples

When adding or modifying examples under `examples/`:

- Use `examples/_defaults.py` for trading costs and stock codes (stamp duty 0.05%, commission 0.025%, minimum 5 CNY)
- Include a module docstring with number, title, description, and teaching objectives
- Add an `if __name__ == "__main__":` guard
- Update both example indices: `examples/README.md` and `docs/examples/index.md` (plus its `.en.md`)

## Commit Messages

Use conventional prefixes:

| Prefix | Use for |
|--------|---------|
| `docs:` | Documentation (always update both `.md` and `.en.md`) |
| `fix:` | Bug fixes |
| `feat:` | New features or examples |
| `chore:` | Cleanup, reorganization |
| `refactor:` | Code restructuring without behavior change |

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
