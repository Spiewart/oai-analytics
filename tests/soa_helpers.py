"""Inline frames for incident-SOA period tests (one participant per frame)."""

import polars as pl

from oai.derive.incident_soa import EXPOSURE_VISITS, OUTCOME_VISITS, Cohort


def person(id_=1, **extra):
    row = dict(ID=id_, age=60.0, sex=1, bmi=28.0, kl0=1.0, sx0=False, womac0=2.0)
    row["subgroup"] = "noroa_nosx"
    return {**row, **extra}


def inline_cohort(*people):
    return Cohort(people=pl.DataFrame(list(people)), flow=pl.DataFrame())


def inline_soa(id_, outcomes, visits=OUTCOME_VISITS):
    """outcomes: soa at each outcome visit (default V01, V03, V05, V06; None = missing)."""
    visits = ["00", *visits]
    return pl.DataFrame(
        {"ID": [id_] * len(visits), "visit": visits, "soa": [False, *outcomes]},
        schema={"ID": pl.Int64, "visit": pl.String, "soa": pl.Boolean},
    )


def inline_crepitus(id_, s2, exam=(0, 0, 0, 0), visits=EXPOSURE_VISITS):
    """s2, exam: values at each exposure visit (default V00, V01, V03, V05; None = missing)."""
    return pl.DataFrame(
        {
            "ID": [id_] * len(visits),
            "SIDE": ["R"] * len(visits),
            "visit": list(visits),
            "koos_s2": list(s2),
            "exam_crepitus": list(exam),
        },
        schema={
            "ID": pl.Int64,
            "SIDE": pl.String,
            "visit": pl.String,
            "koos_s2": pl.Int64,
            "exam_crepitus": pl.Int64,
        },
    )
