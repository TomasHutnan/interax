from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection
from psycopg.rows import DictRow

from app.auth import require_user
from app.db import get_conn

router = APIRouter(
    prefix="/api/regimens", tags=["regimens"], dependencies=[Depends(require_user)]
)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/find")
def find_regimens(
    conn: Annotated[Connection[DictRow], Depends(get_conn)],
    text: str = "",
) -> list[str]:
    """Regimens whose name contains `text` (case-insensitive); all regimens if empty.

    Ordered by exact match, then prefix match, then name.
    """
    query = _escape_like(text.strip().lower())
    rows = conn.execute(
        """
        SELECT concept_name
        FROM concept
        WHERE domain_id = 'Regimen'
          AND concept_class_id = 'Regimen'
          AND invalid_reason IS NULL
          AND lower(concept_name) LIKE %(contains)s
        ORDER BY lower(concept_name) LIKE %(exact)s DESC,
                 lower(concept_name) LIKE %(prefix)s DESC,
                 concept_name
        """,
        {"contains": f"%{query}%", "exact": query, "prefix": f"{query}%"},
    ).fetchall()
    return [row["concept_name"] for row in rows]


@router.get("/components")
def regimen_components(
    name: Annotated[str, Query(min_length=1)],
    conn: Annotated[Connection[DictRow], Depends(get_conn)],
) -> list[str]:
    """Drugs (HemOnc 'Component' concepts) used in a regimen, looked up by name.

    Matching is case-insensitive and exact. The name is a query parameter because
    regimen names can contain '/' (e.g. "FOLFOX 7/sLV5FU2").
    """
    matches = len(
        conn.execute(
            """
            SELECT concept_id
            FROM concept
            WHERE lower(concept_name) = lower(btrim(%s))
              AND domain_id = 'Regimen'
              AND concept_class_id = 'Regimen'
              AND invalid_reason IS NULL
            """,
            (name,),
        ).fetchall()
    )
    if matches == 0:
        raise HTTPException(status_code=404, detail="regimen not found")
    if matches > 1:
        raise HTTPException(
            status_code=409, detail=f"regimen name is ambiguous ({matches} matches)"
        )

    rows = conn.execute("SELECT * FROM regimen_components(%s)", (name,)).fetchall()
    return [row["concept_name"] for row in rows]
