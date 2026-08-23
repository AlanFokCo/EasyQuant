# Python 3.10 four-target hash lock

`constraints-py310.txt` is the hash-checked closure for the release
dependencies plus the `dev` extra on these explicit targets:

- CPython 3.10.0 macOS arm64
- CPython 3.10.20 macOS arm64
- CPython 3.10.0 manylinux x86_64
- CPython 3.10.20 manylinux x86_64

It keeps platform conditions in the lock: `akracer` and `py-mini-racer` are
Linux-only, while `mini-racer` is active everywhere except Linux.

## Generation

Use a clean Python 3.10 environment outside the repository. First retain a
`pip-compile` baseline from `pyproject.toml`; this is the direct Python 3.10
input resolution required by the release workflow:

```bash
python3.10 -m venv /private/tmp/eqlib-lock-py310
/private/tmp/eqlib-lock-py310/bin/python -m pip install pip-tools==7.6.1
/private/tmp/eqlib-lock-py310/bin/pip-compile \
  --allow-unsafe --extra=dev --generate-hashes --no-emit-find-links \
  --output-file /private/tmp/eqlib-pip-compile-base.txt pyproject.toml
```

The four-target branch comes from `uv 0.12.5` in universal mode. It emits
explicit platform markers; the selector keeps only entries active for the four
Python 3.10 target environments above. Run the commands from the repository
root:

```bash
uv pip compile pyproject.toml --extra dev --python python3.10 --python-version 3.10 \
  --universal --generate-hashes --no-strip-markers --no-progress \
  --output-file /private/tmp/eqlib-universal.txt
python requirements/select_py310_targets.py \
  /private/tmp/eqlib-universal.txt requirements/constraints-py310.txt
```

Finally, replace each generated hash block with the sorted union of official PyPI release hashes. The operation is sequential and bounded; it fails before
replacing the output if any entry or response is malformed.

```bash
python requirements/enrich_pypi_hashes.py \
  requirements/constraints-py310.txt requirements/constraints-py310.txt \
  --project-root . --timeout 8 --retries 2 --deadline 300 \
  --max-entries 200 --max-files 500
```

The normal `pip-compile` command may exceed its bounded network deadline. In
that case, do not treat a retry as a fresh resolution: seed a temporary output
from the already validated lock and use `--no-upgrade --reuse-hashes` only to
re-emit the known Python 3.10 baseline. The `uv` universal command above is
the fresh dual-target resolver step.

## Checked resolver evidence

`constraints-py310-resolver-evidence.json` binds the exact lock SHA-256 and
lock-input fingerprint to deterministic active-pin maps for all four targets.
The 3.10.0 maps are evaluated from the marker-preserving universal output; the
3.10.20 maps come from explicit platform-targeted UV resolves. Regenerate the
evidence after regenerating the lock:

```bash
uv pip compile pyproject.toml --extra dev --python python3.10 --python-version 3.10.20 \
  --python-platform aarch64-apple-darwin --no-header --no-annotate --no-progress \
  --output-file /private/tmp/eqlib-macos-cp31020.txt
uv pip compile pyproject.toml --extra dev --python python3.10 --python-version 3.10.20 \
  --python-platform x86_64-manylinux_2_17 --no-header --no-annotate --no-progress \
  --output-file /private/tmp/eqlib-linux-cp31020.txt
python requirements/generate_target_lock_evidence.py \
  requirements/constraints-py310.txt requirements/constraints-py310-resolver-evidence.json \
  --universal-resolved /private/tmp/eqlib-universal.txt \
  --macos-resolved /private/tmp/eqlib-macos-cp31020.txt \
  --linux-resolved /private/tmp/eqlib-linux-cp31020.txt
```

This is checked resolver evidence, not a host-independent runtime install
proof. Task 9 will run the native target gate before CI accepts a refresh.

## What the fingerprint guarantees

The `# eqlib-lock-input-sha256: v1:...` header covers canonical primary and
`dev` declarations, `Requires-Python`, the explicit marker target matrix, and
the resolver/generator pipeline schema. It detects changed lock inputs or a
wrong generation recipe. It does not reproduce a future mutable-index
resolution from the digest alone; rerun the bounded resolver steps to refresh
upstream pins.

## Validation and installation

Validate the Linux target resolver graph without weakening dependency
resolution. This comparison fails if a platform-marker transitive dependency
such as `exceptiongroup` is omitted from the lock:

```bash
uv pip compile pyproject.toml --extra dev --python python3.10 --python-version 3.10.20 \
  --python-platform x86_64-manylinux_2_17 --no-header --no-annotate \
  --no-progress --output-file /private/tmp/eqlib-linux-cp310.txt
python requirements/verify_target_lock.py requirements/constraints-py310.txt \
  /private/tmp/eqlib-linux-cp310.txt --platform linux --python-full-version 3.10.20
```

On a native Linux CPython 3.10 runner, also require a dependency-resolving
strict download (with no `--no-deps`) before CI accepts a refresh:

```bash
python3.10 -m pip download --require-hashes \
  -r requirements/constraints-py310.txt --dest /private/tmp/eqlib-linux-download
```

Cross-target `pip download --platform ... --only-binary=:all:` is not a
closure proof here: `jsonpath` is source-only, and pip forbids a source-capable
cross-target dependency resolution. The native Linux command or the `uv` comparison above provides the intended closure check; `--no-deps` does not prove closure.

For macOS arm64, use a fresh native Python 3.10 venv outside the repository:

```bash
python3.10 -m venv /private/tmp/eqlib-macos-lock
/private/tmp/eqlib-macos-lock/bin/python -m pip install --isolated --no-cache-dir \
  --require-hashes -r requirements/constraints-py310.txt
/private/tmp/eqlib-macos-lock/bin/python -m pip check --isolated
```

Install the local project in two stages only after the third-party lock passes:

```bash
pip install --require-hashes -r requirements/constraints-py310.txt
pip install --no-deps -e ".[dev]"
```
