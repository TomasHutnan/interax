import json
import os
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import requests
from dotenv import load_dotenv

BLOCK_SIZE = 5
ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
if not ROOT_ENV_FILE.exists():
    ROOT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

load_dotenv(ROOT_ENV_FILE, override=False)
load_dotenv(override=False)

RXLABEL_BASE_URL = os.getenv("RXLABEL_BASE_URL", "").rstrip("/")
RXLABEL_API_KEY = os.getenv("RXLABEL_API_KEY", "")


@dataclass
class Interaction:
    substance_1: str
    substance_2: str
    description: str
    severity: str


def get_interactions(substances: list[str]) -> list[Interaction]:
    if len(substances) <= 10:
        return __fetch_interactions(substances)

    interactions: list[Interaction] = []
    for combination in __generate_substance_combinations(substances):
        interactions.extend(__fetch_interactions(combination))

    return __deduplicate_interactions(interactions)


def __generate_substance_combinations(
    substances: list[str],
) -> list[list[str]]:
    assert len(substances) > 10

    blocks = [
        substances[i : i + BLOCK_SIZE] for i in range(0, len(substances), BLOCK_SIZE)
    ]

    return [block1 + block2 for block1, block2 in combinations(blocks, 2)]


def __deduplicate_interactions(interactions: list[Interaction]) -> list[Interaction]:
    seen_interaction: set[tuple[str, str]] = set()
    deduplicated_interactions: list[Interaction] = []

    for item in interactions:
        sub1 = item.substance_1
        sub2 = item.substance_2
        if (sub1, sub2) not in seen_interaction:
            seen_interaction.add((sub1, sub2))
            seen_interaction.add((sub2, sub1))

            deduplicated_interactions.append(item)

    return deduplicated_interactions


def __fetch_interactions(substances: list[str]) -> list[Interaction]:
    if len(substances) < 2:
        return []

    url = (
        f"{RXLABEL_BASE_URL}/interactions/check"
        if RXLABEL_BASE_URL.endswith("/v1")
        else f"{RXLABEL_BASE_URL}/v1/interactions/check"
    )

    headers = {
        "Content-Type": "application/json",
        "x-api-key": RXLABEL_API_KEY,
    }
    payload = {
        "drugs": substances,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    data = response.json()
    pairs = data.get("pairs", [])
    if isinstance(pairs, str):
        pairs = json.loads(pairs)

    interactions: list[Interaction] = []
    for pair in pairs:
        if "drugA" not in pair or "drugB" not in pair or "maxSeverity" not in pair:
            continue

        pair_interactions = pair.get("interactions", [])
        if isinstance(pair_interactions, str):
            pair_interactions = json.loads(pair_interactions)

        for interaction in pair_interactions:
            mechanism = interaction.get("mechanism") or ""
            severity = interaction.get("severity") or "unknown"
            interactions.append(
                Interaction(
                    substance_1=pair["drugA"],
                    substance_2=pair["drugB"],
                    description=mechanism,
                    severity=severity,
                )
            )

    return interactions


__request_interactions = __fetch_interactions
