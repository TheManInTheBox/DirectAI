"""
Load test: fire concurrent chat completion requests to trigger KEDA scale-up.
Usage: python scripts/load-test-chat.py --concurrency 10 --duration 120

Chat completions are much slower than embeddings (~1-5s per request),
so fewer concurrent workers are needed to saturate the backend.
"""

import argparse
import asyncio
import time
import statistics

import httpx

API_URL = "https://api.agilecloud.ai/v1/chat/completions"
API_KEY = "dai_sk_a19d80a7eef73820270555e93bbf95a37881ccfcad9f960196063498487af1e8"

PAYLOAD = {
    "model": "qwen2.5-3b-instruct",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant. Be concise."},
        {"role": "user", "content": "Explain the concept of tensor parallelism in three sentences."},
    ],
    "max_tokens": 100,
    "stream": False,
}

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


async def fire_request(client: httpx.AsyncClient, results: list[dict]):
    """Send one chat completion request and record timing + token counts."""
    t0 = time.monotonic()
    try:
        resp = await client.post(API_URL, json=PAYLOAD, headers=HEADERS, timeout=120.0)
        elapsed = time.monotonic() - t0
        entry = {"status": resp.status_code, "latency": elapsed}
        if resp.status_code == 200:
            body = resp.json()
            usage = body.get("usage", {})
            entry["prompt_tokens"] = usage.get("prompt_tokens", 0)
            entry["completion_tokens"] = usage.get("completion_tokens", 0)
        results.append(entry)
    except Exception as e:
        elapsed = time.monotonic() - t0
        results.append({"status": -1, "latency": elapsed, "error": str(e)})


async def worker(client: httpx.AsyncClient, results: list[dict], stop_event: asyncio.Event):
    """Continuously fire requests until stop_event is set."""
    while not stop_event.is_set():
        await fire_request(client, results)


async def main(concurrency: int, duration: int):
    print(f"\U0001f680 Chat load test: {concurrency} concurrent workers for {duration}s")
    print(f"   Target: {API_URL}")
    print(f"   Model:  {PAYLOAD['model']}")
    print(f"   Max tokens: {PAYLOAD['max_tokens']}")
    print()

    results: list[dict] = []
    stop_event = asyncio.Event()

    async with httpx.AsyncClient(http2=True, verify=True) as client:
        # Warm up with one request
        print("Warming up...", end=" ", flush=True)
        await fire_request(client, results)
        warmup = results.pop()
        print(f"done ({warmup['latency']:.2f}s, status={warmup['status']})")
        print()

        # Launch workers
        t_start = time.monotonic()
        workers = [asyncio.create_task(worker(client, results, stop_event)) for _ in range(concurrency)]

        # Print progress every 10s
        while time.monotonic() - t_start < duration:
            await asyncio.sleep(10)
            elapsed = time.monotonic() - t_start
            ok = sum(1 for r in results if r["status"] == 200)
            err = len(results) - ok
            rps = len(results) / elapsed if elapsed > 0 else 0
            tokens = sum(r.get("completion_tokens", 0) for r in results if r["status"] == 200)
            print(f"  [{elapsed:5.0f}s] {len(results):>5} requests ({ok} ok, {err} err) | {rps:.1f} req/s | {tokens} completion tokens")

        stop_event.set()
        await asyncio.gather(*workers, return_exceptions=True)

    # Summary
    total_time = time.monotonic() - t_start
    ok_results = [r for r in results if r["status"] == 200]
    err_results = [r for r in results if r["status"] != 200]
    total_prompt = sum(r.get("prompt_tokens", 0) for r in ok_results)
    total_completion = sum(r.get("completion_tokens", 0) for r in ok_results)

    print()
    print("=" * 60)
    print(f"  Duration:          {total_time:.1f}s")
    print(f"  Total:             {len(results)} requests")
    print(f"  Success:           {len(ok_results)} ({100*len(ok_results)/max(len(results),1):.1f}%)")
    print(f"  Errors:            {len(err_results)}")
    print(f"  Throughput:        {len(results)/total_time:.1f} req/s")
    print(f"  Prompt tokens:     {total_prompt}")
    print(f"  Completion tokens: {total_completion}")
    print(f"  Tokens/s:          {total_completion/total_time:.1f} tok/s")

    if ok_results:
        lats = [r["latency"] for r in ok_results]
        print(f"  Latency p50:       {statistics.median(lats)*1000:.0f}ms")
        print(f"  Latency p95:       {sorted(lats)[int(len(lats)*0.95)]*1000:.0f}ms")
        print(f"  Latency p99:       {sorted(lats)[int(len(lats)*0.99)]*1000:.0f}ms")
        print(f"  Latency max:       {max(lats)*1000:.0f}ms")

    if err_results:
        print()
        print("  Error breakdown:")
        from collections import Counter
        for status, count in Counter(r["status"] for r in err_results).most_common():
            sample = next(r for r in err_results if r["status"] == status)
            msg = sample.get("error", "")
            print(f"    status={status}: {count}" + (f" ({msg[:80]})" if msg else ""))

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DirectAI chat completions load test")
    parser.add_argument("--concurrency", "-c", type=int, default=10, help="Concurrent workers")
    parser.add_argument("--duration", "-d", type=int, default=120, help="Test duration (seconds)")
    args = parser.parse_args()
    asyncio.run(main(args.concurrency, args.duration))
