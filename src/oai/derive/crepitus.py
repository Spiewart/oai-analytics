"""Crepitus measures in AllClinical: column templates and per-visit values.

Three measures carry crepitus (the Contents PDFs are authoritative; the templates were
checked against every visit's header):

- `exam_crepitus`: examiner-rated patello-femoral crepitus, yes/no (V00, V01, V03, V05, V06, V12)
- `exam_grind_pain`: examiner-rated painful or tender patellar grind, yes/no (V00 to V06 clinic visits)
- `koos_s2`: KOOS S2 self-report, 0 Never .. 4 Always, last 7 days (V00 to V12)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial

import polars as pl

from oai.derive.knee import find_col
from oai.loader import read_table


@dataclass(frozen=True)
class Measure:
    name: str
    template: str
    kind: str  # "binary" (1 = present) or "ordinal" (0..4)
    label: str


MEASURES = (
    Measure("exam_crepitus", "V{visit}{side}KPFCRE", "binary", "Exam: patello-femoral crepitus"),
    Measure(
        "exam_grind_pain", "V{visit}{side}KPGDPN", "binary", "Exam: patellar grind, painful/tender"
    ),
    Measure(
        "koos_s2", "V{visit}KSX{side}KN2", "ordinal", "KOOS S2: grinding/clicking/noise, 7 days"
    ),
)


def measure(name: str) -> Measure:
    """The measure called `name`; KeyError if there is none."""
    for m in MEASURES:
        if m.name == name:
            return m
    raise KeyError(f"no crepitus measure {name!r} (known: {', '.join(m.name for m in MEASURES)})")


def crepitus_values(
    visit: str, names: Sequence[str], sides: Sequence[str] = ("R", "L")
) -> pl.DataFrame:
    """ID, SIDE, visit and one Int64 column per measure name, one row per participant and side.

    Raises KeyError when the visit's AllClinical table has no column for a measure.
    """
    df = read_table("allclinical", visit)
    col = partial(find_col, df, where=f"allclinical{visit}")
    return pl.concat(
        [
            df.select(
                pl.col(col("ID")).cast(pl.Int64).alias("ID"),
                pl.lit(side).alias("SIDE"),
                pl.lit(visit).alias("visit"),
                *[
                    pl.col(col(measure(n).template.format(visit=visit, side=side)))
                    .cast(pl.Int64, strict=False)
                    .alias(n)
                    for n in names
                ],
            )
            for side in sides
        ]
    )
