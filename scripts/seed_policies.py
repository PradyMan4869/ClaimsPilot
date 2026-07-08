"""Seed MongoDB with the demo policies (idempotent).

Usage: python scripts/seed_policies.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.policies import PolicyStore


def main() -> None:
    store = PolicyStore()
    count = store.seed()
    print(f"Backend: {store.backend} — {count} policies available")


if __name__ == "__main__":
    main()
