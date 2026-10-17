from typing import Annotated

from fastapi import APIRouter, Body

try:
    from interactions.interactions import get_interactions
except ModuleNotFoundError:
    from server.interactions.interactions import get_interactions

router = APIRouter(prefix="/api/interactions", tags=["interactions"])


def _find_substance_index(name: str, substances: list[str]) -> int | None:
    name_norm = name.strip().lower()
    # 1. Exact match (case-insensitive)
    for idx, sub in enumerate(substances):
        if sub.strip().lower() == name_norm:
            return idx

    # 2. Substring match
    for idx, sub in enumerate(substances):
        sub_norm = sub.strip().lower()
        if sub_norm in name_norm or name_norm in sub_norm:
            return idx

    return None


@router.post("")
@router.post("/")
def check_interactions(
    substances: Annotated[list[str], Body(embed=True)],
) -> list[tuple[int, int, str, str]]:
    """Check drug interactions for a list of substances.

    Returns a list of interactions formatted as [ia, ib, reason, severity],
    where ia and ib are indices in the given substances list.
    """
    if len(substances) < 2:
        return []

    interactions = get_interactions(substances)
    results: list[tuple[int, int, str, str]] = []

    for item in interactions:
        ia = _find_substance_index(item.substance_1, substances)
        ib = _find_substance_index(item.substance_2, substances)

        if ia is not None and ib is not None and ia != ib:
            description = " ".join(
                filter(
                    None,
                    [
                        item.pathophysiological_mechanism,
                        item.clinical_consequence,
                    ],
                )
            )
            results.append((ia, ib, description, item.severity))

    return results
