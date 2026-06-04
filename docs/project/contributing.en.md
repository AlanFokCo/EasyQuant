# Contributing to EasyQuant

Thank you for your interest in contributing to EasyQuant! We welcome contributions of all kinds — bug reports, feature requests, documentation improvements, and code.

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
4. Run the test suite: `pytest tests/ -v`
5. Commit with a clear message: `git commit -m "feat: add XYZ support"`
6. Push and open a PR against `main`

### Code Style

- Follow PEP 8 conventions
- Use type hints where practical
- Keep functions focused and well-named
- Add docstrings for public API functions

### Documentation

- Update `doc/` or `tutorials/` for user-facing changes
- Run `mkdocs build --strict` locally to verify docs build cleanly
- Bilingual labels (Chinese/English) are preferred for doc headings

## Development Setup

```bash
pip install -e ".[dev,docs]"
pytest tests/ -v
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
