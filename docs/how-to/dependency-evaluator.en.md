# Run the eqlib Adversarial Dependency Evaluator

The built-in `eqlib` evaluator checks release quality across dependencies, wheel metadata, offline contracts, performance baselines, and bounded live-data contracts. It writes both human-readable Markdown and CI-consumable JSON evidence.

## Run the offline audit

From the repository root, using Python 3.10 or later:

```bash
python scripts/evaluate_eqlib_dependencies.py \
  --profile offline --strict --output artifacts/eqlib-evaluator
```

The output is `artifacts/eqlib-evaluator/report.md` and `report.json`. With `--strict`, P0/P1 findings produce a non-zero exit code. P2 findings, such as an unavailable comparable performance baseline, are recorded but do not block a commit.

Offline contracts explicitly exclude `pytest.mark.network`, so they do not contact market-data providers. They cover imports, market-data adapter boundaries, the trading calendar, portfolio risk, statistics, and ML preprocessing.

## Run the bounded live audit

The live profile runs only tests explicitly marked `network`:

```bash
python scripts/evaluate_eqlib_dependencies.py \
  --profile live --output artifacts/eqlib-evaluator-live
```

This profile sets `EQLIB_EVALUATOR_LIVE=1` and has a 90-second total deadline. Provider unavailability or a timeout becomes `DATA-190` with status `unavailable`; it is never reported as a passing product check. GitHub Actions runs this mode on weekdays and by manual dispatch, while ordinary pushes and PRs use the strict offline gate.

## Read findings

| Severity | Meaning | Strict offline gate |
| --- | --- | --- |
| P0 | Incorrect results, installability, or data-integrity risk | Blocks |
| P1 | Reliability, contract, or reproducibility risk | Blocks |
| P2 | Performance, observability, or temporarily unavailable supporting evidence | Recorded, not blocking |

The `evidence` field preserves commands, exit codes, failed pytest node IDs, and bounded logs. Do not rely only on the report summary; rerun the same profile after a fix.

## Refresh the lock

The Python 3.10 four-target hash lock and checked resolver evidence are under `requirements/`. Do not edit the lock by hand. Follow the generation, hash enrichment, and target-validation steps in `requirements/README.md` at the repository root. After a refresh, run the strict offline evaluator and perform the strict lock download on native Linux Python 3.10.

## CI behavior

`.github/workflows/eqlib-evaluator.yml` runs the strict offline audit on Ubuntu with Python 3.10 and 3.12, then uploads reports. Its scheduled/manual live job uploads the online report. The normal test workflow uses `-m "not network"` to exclude real provider calls so network fluctuation cannot affect reproducible tests.

The offline report also checks that the packaged trading calendar covers at least the next 120 days. Near expiry it emits `DATA-192` (P2), prompting a refresh of `eqlib/static/ashare_trading_days.json` before the next release.
