"""Generate 50-100 synthetic claim documents using the local LLM.

Each document is a realistic first-person claim letter over a structured header
(claimant, policy, date, type, amount) whose values are sampled to exercise every
pipeline path: valid claims, lapsed policies, uncovered incident types, amounts
over limit, unknown policies, and claims above the auto-approve threshold.

If LM Studio is offline the narrative falls back to templates — the documents are
still fully usable (the header carries the ground truth either way).

Usage: python scripts/generate_claims.py [--count 60]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.llm import LocalLLM
from db.policies import SEED_POLICIES

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "claims"

INCIDENT_TYPES = ["accident", "theft", "fire", "flood"]

NARRATIVE_PROMPT = """\
Write a 4-6 sentence first-person account of an insurance incident for a claim letter.
Incident type: {incident_type}. Date: {incident_date}. Estimated loss: {amount}.
Keep it factual and plain; do not restate the policy number or claimant name.
"""

TEMPLATE_NARRATIVES = {
    "accident": "On the date above my vehicle was involved in a collision at a junction. "
    "The other party ran a red light and struck the passenger side. Photographs and a "
    "police report are available on request.",
    "theft": "My insured property was stolen from the premises overnight. I discovered "
    "the loss the following morning and reported it to the police the same day.",
    "fire": "A fire broke out in the kitchen and spread to adjoining rooms before the "
    "fire service contained it. The affected area and contents sustained heavy damage.",
    "flood": "Heavy rainfall caused water ingress into the ground floor of the property. "
    "Flooring, furniture and electrical fittings were damaged before the water receded.",
}


def sample_scenario(rng: random.Random) -> dict:
    """Sample one claim scenario, biased to cover all decision paths."""
    policy = rng.choice(SEED_POLICIES)
    scenario = rng.choices(
        ["clean", "over_limit", "uncovered_type", "unknown_policy", "big_amount", "early_incident"],
        weights=[40, 12, 12, 12, 14, 10],
    )[0]

    incident_type = rng.choice(policy["covered_incident_types"])
    amount = round(rng.uniform(1000, 9000), -1)
    policy_number = policy["policy_number"]
    incident_date = date(2024, 1, 1) + timedelta(days=rng.randint(60, 700))

    if scenario == "over_limit":
        amount = policy["coverage_limit"] * rng.uniform(1.1, 2.0)
    elif scenario == "uncovered_type":
        uncovered = [t for t in INCIDENT_TYPES if t not in policy["covered_incident_types"]]
        incident_type = rng.choice(uncovered) if uncovered else "other"
    elif scenario == "unknown_policy":
        policy_number = f"POL-{rng.randint(9000, 9999)}"
    elif scenario == "big_amount":
        amount = rng.uniform(12000, min(policy["coverage_limit"], 40000))  # escalation path
    elif scenario == "early_incident":
        incident_date = date(2023, 1, 1) + timedelta(days=rng.randint(0, 25))  # waiting period

    return {
        "claimant_name": policy["holder_name"],
        "policy_number": policy_number,
        "incident_date": incident_date.isoformat(),
        "incident_type": incident_type,
        "claim_amount": round(amount, 2),
        "scenario": scenario,
    }


def render_document(scenario: dict, narrative: str) -> str:
    return (
        "INSURANCE CLAIM SUBMISSION\n"
        "==========================\n"
        f"Claimant Name: {scenario['claimant_name']}\n"
        f"Policy Number: {scenario['policy_number']}\n"
        f"Incident Date: {scenario['incident_date']}\n"
        f"Incident Type: {scenario['incident_type']}\n"
        f"Claim Amount: ${scenario['claim_amount']:,.2f}\n"
        "\nSTATEMENT OF LOSS\n-----------------\n"
        f"{narrative}\n\n"
        "I declare the above information to be true and complete.\n"
        f"Signed: {scenario['claimant_name']}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic claim documents")
    parser.add_argument("--count", type=int, default=60, help="number of documents (50-100 typical)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    llm = LocalLLM()
    llm_up = llm.is_available()
    print(f"LM Studio {'available — LLM narratives' if llm_up else 'offline — template narratives'}")

    manifest = []
    for i in range(1, args.count + 1):
        scenario = sample_scenario(rng)
        narrative = None
        if llm_up:
            narrative = llm.complete(
                "You write realistic insurance claim statements.",
                NARRATIVE_PROMPT.format(
                    incident_type=scenario["incident_type"],
                    incident_date=scenario["incident_date"],
                    amount=f"${scenario['claim_amount']:,.2f}",
                ),
                temperature=0.8,
            )
        narrative = narrative or TEMPLATE_NARRATIVES.get(scenario["incident_type"], "Loss occurred as described.")

        filename = f"claim_{i:03d}.txt"
        (OUTPUT_DIR / filename).write_text(render_document(scenario, narrative), encoding="utf-8")
        manifest.append({"file": filename, **scenario})
        print(f"  wrote {filename}  [{scenario['scenario']}]")

    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n{args.count} documents + manifest.json written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
