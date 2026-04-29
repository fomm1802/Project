import asyncio
import statistics
import time


def fmt(ms: float) -> str:
    return f"{ms:,.2f} ms"


async def fake_io(latency_ms: int = 120):
    await asyncio.sleep(latency_ms / 1000)
    return True


async def run_sequential(n: int, latency_ms: int):
    start = time.perf_counter()
    for _ in range(n):
        await fake_io(latency_ms)
    return (time.perf_counter() - start) * 1000


async def run_concurrent_bounded(n: int, latency_ms: int, limit: int):
    sem = asyncio.Semaphore(limit)

    async def worker():
        async with sem:
            return await fake_io(latency_ms)

    start = time.perf_counter()
    await asyncio.gather(*(worker() for _ in range(n)))
    return (time.perf_counter() - start) * 1000


async def sample(title: str, fn, rounds: int = 5):
    samples = []
    for _ in range(rounds):
        samples.append(await fn())
    avg = statistics.mean(samples)
    p95 = sorted(samples)[max(0, int(rounds * 0.95) - 1)]
    print(f"{title}: avg={fmt(avg)} | p95={fmt(p95)} | runs={[round(x,2) for x in samples]}")
    return avg


async def main():
    print("=== Concurrency Benchmark (Synthetic I/O) ===")
    print("Scenario A: config warmup, N=100, latency=100ms")
    seq_a = await sample("A-sequential", lambda: run_sequential(100, 100))
    con_a = await sample("A-concurrent(limit=20)", lambda: run_concurrent_bounded(100, 100, 20))
    print(f"A speedup: {seq_a/con_a:.2f}x")

    print("\nScenario B: invite sync, N=60, latency=120ms")
    seq_b = await sample("B-sequential", lambda: run_sequential(60, 120))
    con_b = await sample("B-concurrent(limit=5)", lambda: run_concurrent_bounded(60, 120, 5))
    print(f"B speedup: {seq_b/con_b:.2f}x")


if __name__ == "__main__":
    asyncio.run(main())
