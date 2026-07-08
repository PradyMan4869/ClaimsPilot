"""Launch all three A2A agent servers as subprocesses and wait.

Usage: python scripts/start_agents.py     (Ctrl+C stops all)
Each agent is an independent process — kill one and the others keep serving,
which is exactly the failure isolation A2A is meant to provide.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import httpx

from common.config import settings

AGENTS = [
    ("agents.extractor", settings.extractor_url),
    ("agents.validator", settings.validator_url),
    ("agents.responder", settings.responder_url),
]


def main() -> None:
    processes: list[subprocess.Popen] = []
    try:
        for module, url in AGENTS:
            proc = subprocess.Popen([sys.executable, "-m", module], cwd=PROJECT_ROOT)
            processes.append(proc)
            print(f"started {module} (pid {proc.pid}) at {url}")

        print("\nwaiting for agent cards", end="", flush=True)
        deadline = time.time() + 60
        pending = {url for _, url in AGENTS}
        while pending and time.time() < deadline:
            for url in list(pending):
                try:
                    response = httpx.get(url + "/.well-known/agent-card.json", timeout=2)
                    if response.status_code == 200:
                        pending.discard(url)
                        print(f"\n  ✓ {response.json()['name']} — {url}", flush=True)
                except httpx.HTTPError:
                    pass
            if pending:
                print(".", end="", flush=True)
                time.sleep(1)

        if pending:
            print(f"\nWARNING: no agent card from: {pending}")
        else:
            print("\nAll agents up. Ctrl+C to stop.")
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print("\nstopping agents…")
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()


if __name__ == "__main__":
    main()
