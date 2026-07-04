#!/usr/bin/env python3
"""Fire a realistic mixed workload at a running Arbiter and watch savings grow.

This is the demo driver: start the proxy, run this, and the dashboard fills in
as the router explores every model and then settles on the cheap-but-good one
for each task type. It prints a running savings line so it reads well in a
terminal recording too.

    python scripts/bench.py --n 300 --fresh
"""
import argparse
import random
import sys
import time

import httpx

# A spread of prompts per task type. Kept concrete so the objective scorers
# (code parses, math matches, JSON is valid) actually have something to check.
PROMPTS: dict[str, list[str]] = {
    "code": [
        "Write a Python function that returns the nth Fibonacci number.",
        "Write a Python function to check whether a string is a palindrome.",
        "Write a JavaScript function that flattens a nested array.",
        "Write a Python function to count vowels in a string.",
        "Implement binary search in Python and return the index or -1.",
        "Write a function to reverse a singly linked list in Python.",
    ],
    "math": [
        "Calculate 37 * 24. Reply with just the number.",
        "Calculate 1024 / 16. Reply with just the number.",
        "Calculate 256 + 744. Reply with just the number.",
        "Calculate 89 * 11. Reply with just the number.",
        "Calculate 5000 - 1375. Reply with just the number.",
        "Calculate 144 + 169. Reply with just the number.",
    ],
    "structured": [
        "Return valid JSON with keys name and age for a person named Ada aged 36.",
        "Return a JSON array of three primary colors.",
        "Return valid JSON describing Tokyo with keys city and country.",
        "Return a JSON object with keys title and year for the film Inception.",
        "Return a JSON array of the first four even numbers.",
    ],
    "factual": [
        "Who wrote the novel Pride and Prejudice?",
        "What is the capital of Australia?",
        "Which planet is known as the Red Planet?",
        "Who painted the Mona Lisa?",
        "What is the largest ocean on Earth?",
    ],
    "open": [
        "Write two sentences about the sound of rain.",
        "Give a one-line motivational thought for a Monday.",
        "Describe the color blue to someone who cannot see.",
        "Write a short haiku about mountains.",
        "Suggest a creative name for a coffee shop.",
    ],
}


def one_request(client: httpx.Client, url: str, max_tokens: int, free: bool) -> None:
    task = random.choice(list(PROMPTS))
    prompt = random.choice(PROMPTS[task])
    body = {
        "model": "auto",  # ignored by Arbiter on purpose
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    if free:
        body["arbiter_max_cost"] = 0  # route only among $0 models
    client.post(f"{url}/v1/chat/completions", json=body)


def _new_key(client: httpx.Client, url: str) -> None:
    """Mint a fresh API key and use it. Rotating keys keeps each one under the
    per-key rate limit, so the benchmark can send unlimited volume."""
    r = client.post(f"{url}/v1/register", json={"email": "bench@arbiter.local"})
    r.raise_for_status()
    client.headers["Authorization"] = f"Bearer {r.json()['api_key']}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--n", type=int, default=300, help="number of requests")
    ap.add_argument("--max-tokens", type=int, default=24, help="reply length (small = cheap)")
    ap.add_argument("--free", action="store_true", help="route only among $0 models")
    ap.add_argument("--fresh", action="store_true", help="reset learned state first")
    args = ap.parse_args()

    with httpx.Client(timeout=120) as client:
        try:
            client.get(f"{args.url}/health").raise_for_status()
        except Exception:
            print(f"Arbiter is not answering at {args.url}. Start it with scripts/dev.sh")
            return 1

        _new_key(client, args.url)

        if args.fresh:
            client.post(f"{args.url}/v1/reset")
            print("reset learned state\n")

        start = time.time()
        on_key = 0
        for i in range(1, args.n + 1):
            if on_key >= 45:  # stay under the 50/6h per-key limit
                _new_key(client, args.url)
                on_key = 0
            one_request(client, args.url, args.max_tokens, args.free)
            on_key += 1
            if i % 20 == 0 or i == args.n:
                rep = client.get(f"{args.url}/v1/report").json()
                avg = rep["actual_spend"] / rep["calls"] if rep["calls"] else 0
                print(f"  {i:5d}/{args.n}  calls={rep['calls']:<6} spend=${rep['actual_spend']:.5f}  avg=${avg:.7f}/call")

        rep = client.get(f"{args.url}/v1/report").json()
        pol = client.get(f"{args.url}/v1/policy").json()
        dur = time.time() - start
        print(f"\nDone: {rep['calls']} calls in {dur:.0f}s, spend ${rep['actual_spend']:.5f}")
        print("\nChosen model per task (cheapest within tolerance of best quality):")
        for task, rows in pol.items():
            rows = [r for r in rows if r["quality"] is not None]
            if not rows:
                continue
            best_q = max(r["quality"] for r in rows)
            ok = [r for r in rows if r["quality"] >= best_q - 0.05]
            pick = min(ok, key=lambda r: r["avg_cost"])
            print(f"  {task:11s} -> {pick['model']:38s} q={pick['quality']:.2f} ${pick['avg_cost']:.7f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
