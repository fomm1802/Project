# Benchmark Results

Date: 2026-04-29 (UTC)
Script: `benchmarks/benchmark_concurrency.py`

## Scenario A — Config warmup simulation
- Workload: 100 I/O tasks, each 100ms latency
- Sequential avg: 10,041.65 ms
- Concurrent (limit=20) avg: 505.92 ms
- Speedup: **19.85x**

## Scenario B — Invite sync simulation
- Workload: 60 I/O tasks, each 120ms latency
- Sequential avg: 7,227.30 ms
- Concurrent (limit=5) avg: 1,447.82 ms
- Speedup: **4.99x**

## Notes
- This is a synthetic benchmark to validate concurrency design, not an end-to-end Discord API benchmark.
- Real-world speed depends on API latency, rate-limits, CPU quota, and host network variability.
