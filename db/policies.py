"""Policy store: MongoDB-backed, with an in-memory fallback of the same seed
data so the whole demo runs without Mongo installed.
"""
from __future__ import annotations

import logging
from datetime import date

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from common.config import settings

logger = logging.getLogger(__name__)

# Seed policies — policy numbers match scripts/generate_claims.py output.
SEED_POLICIES: list[dict] = [
    {
        "policy_number": f"POL-{1000 + i}",
        "holder_name": name,
        "status": "active" if i % 7 != 3 else "lapsed",
        "coverage_start": "2023-01-01",
        "coverage_end": "2026-12-31",
        "coverage_limit": limit,
        "deductible": 500,
        "covered_incident_types": covered,
        "waiting_period_days": 30,
    }
    for i, (name, limit, covered) in enumerate(
        [
            ("Aarav Sharma", 50000, ["accident", "theft", "fire"]),
            ("Priya Nair", 25000, ["accident", "theft"]),
            ("Rohan Mehta", 100000, ["accident", "fire", "flood", "theft"]),
            ("Sneha Iyer", 15000, ["accident"]),
            ("Vikram Rao", 75000, ["accident", "theft", "fire", "flood"]),
            ("Ananya Das", 30000, ["theft", "fire"]),
            ("Karan Kapoor", 60000, ["accident", "flood"]),
            ("Meera Pillai", 20000, ["accident", "theft"]),
            ("Arjun Singh", 45000, ["accident", "fire"]),
            ("Divya Menon", 35000, ["accident", "theft", "fire"]),
        ]
    )
]

VALIDATION_RULES: list[dict] = [
    {"id": "policy_active", "description": "Policy must be active (not lapsed or cancelled)."},
    {"id": "within_coverage_period", "description": "Incident date must fall inside the coverage window."},
    {"id": "incident_type_covered", "description": "Incident type must be listed in covered_incident_types."},
    {"id": "within_coverage_limit", "description": "Claim amount must not exceed the policy coverage limit."},
    {"id": "waiting_period_elapsed", "description": "Incident must occur after the waiting period from coverage start."},
]


class PolicyStore:
    def __init__(self, uri: str | None = None, db_name: str | None = None):
        self.backend = "memory"
        self._memory = {p["policy_number"]: p for p in SEED_POLICIES}
        try:
            client: MongoClient = MongoClient(uri or settings.mongo_uri, serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
            self._collection = client[db_name or settings.mongo_db]["policies"]
            self.backend = "mongodb"
        except PyMongoError as exc:
            logger.warning("MongoDB unavailable (%s) — using in-memory policy store", exc)
            self._collection = None

    def seed(self) -> int:
        """Idempotently load seed policies into Mongo."""
        if self._collection is None:
            return len(self._memory)
        for policy in SEED_POLICIES:
            self._collection.update_one(
                {"policy_number": policy["policy_number"]}, {"$set": policy}, upsert=True
            )
        return self._collection.count_documents({})

    def get_policy(self, policy_number: str) -> dict | None:
        if self._collection is not None:
            doc = self._collection.find_one({"policy_number": policy_number}, {"_id": 0})
            if doc:
                return doc
        return self._memory.get(policy_number)

    @staticmethod
    def get_rules() -> list[dict]:
        return VALIDATION_RULES
