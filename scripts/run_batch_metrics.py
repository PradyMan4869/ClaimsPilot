"""Run every generated claim through the orchestrator and report metrics.

Not part of the core deliverable — a one-off script to produce resume-grade
numbers (latency, throughput, decision distribution, scenario/decision
agreement) from a real batch run traced end-to-end in LangSmith.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.pipeline import ClaimsOrchestrator

CLAIMS_DIR = PROJECT_ROOT / "data" / "claims"

EXPECTED_DECISION = {
    "clean": "approve",
    "big_amount": "escalate",
    "over_limit": "reject",
    "uncovered_type": "reject",
    "unknown_policy": "reject",
    "early_incident": "reject",
}


def main() -> None:
    manifest = json.loads((CLAIMS_DIR / "manifest.json").read_text(encoding="utf-8"))
    orchestrator = ClaimsOrchestrator()

    print("A2A discovery:")
    for name, info in orchestrator.discover().items():
        print(f"  {name} -> {info}")
    print()

    per_agent_latency: dict[str, list[float]] = {"extractor": [], "validator": [], "responder": []}
    total_latencies: list[float] = []
    decisions: list[str] = []
    matches = 0
    errors = 0

    batch_start = time.perf_counter()
    for entry in manifest:
        text = (CLAIMS_DIR / entry["file"]).read_text(encoding="utf-8")
        start = time.perf_counter()
        result = orchestrator.run(text)
        elapsed = time.perf_counter() - start
        total_latencies.append(elapsed)

        for ev in result.events:
            if ev.status == "completed" and ev.agent in per_agent_latency:
                per_agent_latency[ev.agent].append(ev.elapsed_s)

        if result.error:
            errors += 1
            print(f"  {entry['file']:16s} [{entry['scenario']:14s}] ERROR: {result.error}")
            continue

        decisions.append(result.decision)
        expected = EXPECTED_DECISION.get(entry["scenario"])
        agree = result.decision == expected
        matches += int(agree)
        flag = "OK" if agree else "MISMATCH"
        print(f"  {entry['file']:16s} [{entry['scenario']:14s}] -> {result.decision:9s} "
              f"(expected {expected:9s}) {flag}  {elapsed:.2f}s")

    batch_elapsed = time.perf_counter() - batch_start
    n = len(manifest)

    print("\n" + "=" * 60)
    print("METRICS")
    print("=" * 60)
    print(f"Claims processed:        {n}")
    print(f"Errors:                  {errors}")
    print(f"Decision agreement:      {matches}/{n - errors} ({100 * matches / max(1, n - errors):.1f}%)")
    print(f"Decision distribution:   {dict((d, decisions.count(d)) for d in set(decisions))}")
    print(f"Total batch wall time:   {batch_elapsed:.1f}s")
    print(f"Throughput:              {n / batch_elapsed:.2f} claims/sec")
    print(f"End-to-end latency:      mean={statistics.mean(total_latencies):.2f}s  "
          f"p50={statistics.median(total_latencies):.2f}s  "
          f"p95={sorted(total_latencies)[int(0.95 * len(total_latencies)) - 1]:.2f}s  "
          f"max={max(total_latencies):.2f}s")
    for agent, lats in per_agent_latency.items():
        if lats:
            print(f"  {agent:10s} latency:  mean={statistics.mean(lats):.2f}s  "
                  f"p50={statistics.median(lats):.2f}s  max={max(lats):.2f}s")


if __name__ == "__main__":
    main()
