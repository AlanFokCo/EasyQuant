# Python 3.10 hash lock

`constraints-py310.txt` is the reproducible, hash-checked resolution for the
release dependencies and the `dev` extra. Generate it from a clean Python 3.10
environment at the repository root:

```bash
pip-compile --generate-hashes --extra dev --output-file requirements/constraints-py310.txt pyproject.toml
```

`pip-compile` resolves on its host, so the checked-in lock augments each exact
pin's hash block with the sorted union of official PyPI release hashes from
`https://pypi.org/pypi/{distribution}/{version}/json`. This preserves the
Python 3.10 resolution while allowing hash-checked downloads for both the
macOS and CPython 3.10 manylinux artifacts used by the project. Keep this
augmentation sequential and bounded (10 seconds per request, 180 seconds
overall); fail rather than commit a partial hash set:

```bash
python requirements/enrich_pypi_hashes.py \
  requirements/constraints-py310.txt requirements/constraints-py310.txt \
  --timeout 10 --retries 2 --deadline 180 --max-entries 100 --max-files 500
```

The lock header records the pip-compile base command and the augmentation. The
checked-in release header also includes `--allow-unsafe --no-emit-find-links`:
the former pins pip/setuptools selected by pip-tools, and the latter prevents a
temporary local wheelhouse path from becoming lock input. After augmentation,
validate both target platforms with `pip download --require-hashes --no-deps`.

Install in two stages so the hash-checked third-party resolution is installed
before the local editable package:

```bash
pip install --require-hashes -r requirements/constraints-py310.txt
pip install --no-deps -e ".[dev]"
```
