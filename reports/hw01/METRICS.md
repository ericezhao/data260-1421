# Homework 1 Non-Determinism Metrics

- Model: `qwen3:8b`
- Fixed input: `reports/hw01/cases/nondeterminism_input.json`
- Input SHA-256: `8fe9960f63e8379b48eaf43a9f7a07c302f71e3200eb41d4a2fbba438a41761e`
- Latency percentiles: linear interpolation using `(n - 1) * p`.

| Metric | Temp 0.7 | Temp 0.0 |
| --- | --- | --- |
| Completed runs | 20 | 20 |
| Distinct tag sets | 7 | 1 |
| Tags in all runs | `yakitori restaurant inspections` | `restaurant hygiene`, `yakitori restaurant`, `yakitori restaurant inspections` |
| Tags in exactly 1 run | `food safety`, `yakitori hygiene` | None |
| Latency p50 / p95 / p99 (ms) | 15720.0 / 16798.8 / 16871.0 | 12653.5 / 12959.2 / 14179.0 |

## Method Notes

- A tag set is treated as unordered and case-insensitive. The same three tags in a different order count as the same set.
- A tag is counted at most once per run when calculating tags that appeared in all runs or exactly one run.
- Latency measures the complete Planner, Reviewer, and Finalizer pipeline for each run.

## Interpretation

At temperature 0.7, two users submitting the identical input could receive different combinations of tags. The experiment produced seven distinct tag sets, although `yakitori restaurant inspections` appeared in all 20 runs. At temperature 0.0, both users would be much more likely to receive the same output because all 20 runs produced one tag set.

Run-to-run variation is acceptable for brainstorming descriptive tags for a restaurant-inspection article because several different relevant phrases can describe the same content. Variation would not be acceptable for a safety-critical decision, such as determining whether a restaurant passed an inspection or must close, because identical evidence should lead to a consistent result.
