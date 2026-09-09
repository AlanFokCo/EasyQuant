# eqlib adversarial audit remediation

Base: `1922d7c044be07ac31c722ef4b123b69de3b9d6a`.

All sixteen reproduced audit findings have regression coverage and fixes:

| Finding | Fix | Regression suite |
| --- | --- | --- |
| F01 | Paper timestamps use datetimes; failures preserve unprocessed and callback-created orders | `test_adversarial_engine_regressions.py` |
| F02 | Missing/invalid quotes retain the last valid mark and expose `price_stale` | `test_adversarial_engine_regressions.py` |
| F03 | Historical ML feature dates, explicit label availability, training bounds and model rewind checks | `test_ml_point_in_time.py` |
| F04 | Simulation daily prices stop before the current day; minute prices stop before the decision instant | `test_data_adversarial_regressions.py`, `test_minute_visibility.py` |
| F05 | Limit prices constrain execution after slippage | `test_adversarial_engine_regressions.py` |
| F06 | Split orders, repeated matching, aliases and both sides share daily volume capacity | `test_adversarial_engine_regressions.py` |
| F07 | Drawdowns include initial wealth | `test_statistics_audit_regressions.py` |
| F08 | Report drawdowns divide wealth by its running peak | `test_statistics_audit_regressions.py` |
| F09 | CVaR uses the actual tail even when its quantile is positive | `test_statistics_audit_regressions.py` |
| F10 | Public cache/history results are defensive copies | `test_data_adversarial_regressions.py` |
| F11 | Bare/suffixed orders resolve to the same holding; percentage sells use shares; initial dictionary keys stay compatible | `test_adversarial_engine_regressions.py` |
| F12 | Temporarily unfillable orders remain queued | `test_adversarial_engine_regressions.py` |
| F13 | Cancelling partial fills produces a terminal cancelled status | `test_adversarial_engine_regressions.py` |
| F14 | Completion follows filled status; unresolved monetary quantity is explicit | `test_adversarial_engine_regressions.py` |
| F15 | Price APIs validate counts/frequencies and normalize dates before sorted slicing | `test_data_adversarial_regressions.py`, `test_minute_visibility.py` |
| F16 | Adjustment mismatches fail visibly; real raw preload and empty fallback paths remain supported | `test_data_adversarial_regressions.py` |

## Validation

- Core suite including example smoke tests: 1,071 passed, 18 network tests deselected. Outbound sockets were disabled in the test runner to keep this validation deterministic.
- Evaluator suite: 101 passed, including wheel build/metadata and subprocess lifecycle tests.
- Final independent evaluator: 63 relevant regressions passed, plus mixed-alias volume/exit and raw/qfq fallback probes; no remaining blocking findings in the reviewed changes.
- Bilingual documentation synchronization and `mkdocs build --strict` passed.

## Compatibility and scope

External ML labels now require `available_at`; callers must supply when a complete label truly became observable. Daily data during simulation excludes the current day. Minute data excludes the current or future instant. `fq=None` cannot silently reuse qfq data. Monetary order `remaining_amount()` is `None` before its quantity is first resolved. Bilingual API and tutorial documentation describes these contracts.

The existing calendar coverage evaluator remains active: the bundled calendar ends on 2026-12-31 and its 120-day horizon can produce DATA192 as time advances. The profile-routing unit test isolates that unrelated clock-dependent check; calendar contract tests continue to cover the warning. No future exchange dates were fabricated and no evaluator severity or merge gate was weakened. Live provider behavior is outside this offline validation.
