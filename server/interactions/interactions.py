from itertools import combinations
import json
import os
from pathlib import Path

from dotenv import load_dotenv
import requests

BLOCK_SIZE = 5
ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
if not ROOT_ENV_FILE.exists():
    ROOT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

load_dotenv(ROOT_ENV_FILE, override=False)
load_dotenv(override=False)

RXLABEL_BASE_URL = os.getenv(
    "RXLABEL_BASE_URL", "https://api.rxlabelguard.com/v1/"
)
RXLABEL_API_KEY = os.getenv("RXLABEL_API_KEY", "")


def get_interactions(substances: list[str]) -> list[tuple[str, str, str]]:
    if len(substances) <= 10:
        return __fetch_interactions(substances)

    interactions: list[tuple[str, str, str]] = []
    for combination in __generate_substance_combinations(substances):
        interactions.extend(__fetch_interactions(combination))

    return __deduplicate_interactions(interactions)


def __generate_substance_combinations(
    substances: list[str],
) -> list[list[str]]:
    assert len(substances) > 10

    blocks = [
        substances[i:i + BLOCK_SIZE]
        for i in range(0, len(substances), BLOCK_SIZE)
    ]

    return [block1 + block2 for block1, block2 in combinations(blocks, 2)]


def __deduplicate_interactions(
    interactions: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    seen_interaction: set[tuple[str, str]] = set()
    deduplicated_interactions: list[tuple[str, str, str]] = []

    for sub1, sub2, description in interactions:
        if (sub1, sub2) not in seen_interaction:
            seen_interaction.add((sub1, sub2))
            seen_interaction.add((sub2, sub1))

            deduplicated_interactions.append((sub1, sub2, description))

    return deduplicated_interactions


def __fetch_interactions(substances: list[str]) -> list[tuple[str, str, str]]:
    if len(substances) < 2:
        return []

    base_url = os.getenv("RXLABEL_BASE_URL", RXLABEL_BASE_URL).rstrip("/")
    api_key = os.getenv("RXLABEL_API_KEY", RXLABEL_API_KEY)

    url = (
        f"{base_url}/interactions/check"
        if base_url.endswith("/v1")
        else f"{base_url}/v1/interactions/check"
    )

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
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

    interactions: list[tuple[str, str, str]] = []
    for pair in pairs:
        drug_a = pair.get("drugA", "")
        drug_b = pair.get("drugB", "")
        pair_interactions = pair.get("interactions", [])
        if isinstance(pair_interactions, str):
            pair_interactions = json.loads(pair_interactions)

        for interaction in pair_interactions:
            mechanism = interaction.get("mechanism") or ""
            interactions.append((drug_a, drug_b, mechanism))

    return interactions


__request_interactions = __fetch_interactions
