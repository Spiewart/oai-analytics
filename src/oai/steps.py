"""Per-minute GT1M step counts at 48 and 72 months, via a Parquet cache.

The steps are not in the public OAI release. They are SAS files shared by the OAI
accelerometry investigators at Northwestern, kept in OAI_STEPS_DIR (outside the repository
and apart from OAI_DATA_DIR), one file per wave named stepminbymin{visit}*.sas7bdat (any case).
Each row is one ID x PAStudyDay x MINSequence, the same keys as the release's
Acceldatabymin files, so steps join onto the minute counts (oai.derive.accel.read_minutes).

Steps were captured only when the coordinator chose "step counts" at download, so some
participants have no steps at all and a few have gaps; those minutes stay null, never zero.
The cache lives in OAI_WORK_DIR/cache/steps/, which bundles never copy (they skip Parquet).
"""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path

import polars as pl

from oai.config import Settings, get_settings
from oai.derive.knee import find_col
from oai.errors import OAIError
from oai.loader import _replacing

STEP_VISITS = ("06", "08")  # 48 and 72 months: the two accelerometer waves
CACHE_VERSION = 1  # bump when parse_steps changes what it writes
KEYS = ["ID", "day", "minute"]


class StepsError(OAIError):
    """A step file is missing, ambiguous or malformed."""


def step_file(visit: str, settings: Settings | None = None) -> Path:
    """The one SAS step file for `visit` in OAI_STEPS_DIR."""
    if visit not in STEP_VISITS:
        raise StepsError(f"no step data for visit {visit}; step files exist for {STEP_VISITS}")
    folder = (settings or get_settings()).steps_dir
    prefix = f"stepminbymin{visit}"
    found = sorted(
        p
        for p in folder.iterdir()
        if p.name.lower().startswith(prefix) and p.name.lower().endswith(".sas7bdat")
    )
    if not found:
        raise StepsError(f"no step file for visit {visit} ({prefix}*.sas7bdat) in {folder}")
    if len(found) > 1:
        names = ", ".join(p.name for p in found)
        raise StepsError(f"{len(found)} step files for visit {visit} in {folder}: {names}")
    return found[0]


def _read_sas(path: Path) -> pl.DataFrame:
    import pyreadstat  # imported here so the rest of the package does not need it

    df, _ = pyreadstat.read_sas7bdat(path, output_format="polars")
    return df


def parse_steps(raw: pl.DataFrame, visit: str) -> pl.DataFrame:
    """ID, day, minute, steps from one raw step file, sorted; steps null where not captured."""
    col = partial(find_col, raw, where=f"step file {visit}")
    out = raw.select(
        pl.col(col("ID")).cast(pl.Int64).alias("ID"),
        pl.col(col(f"V{visit}PAStudyDay")).cast(pl.Int64).alias("day"),
        pl.col(col(f"V{visit}MINSequence")).cast(pl.Int64).alias("minute"),
        pl.col(col(f"V{visit}MINStep")).cast(pl.Float64).alias("steps"),
    ).sort(KEYS)
    dups = out.height - out.select(KEYS).n_unique()
    if dups:
        raise StepsError(f"step file {visit} has {dups} duplicate ID x day x minute rows")
    s = out["steps"].drop_nulls()
    if ((s < 0) | (s != s.floor())).any():
        raise StepsError(f"step file {visit}: steps must be whole numbers >= 0")
    return out


def _meta(path: Path) -> dict[str, object]:
    st = path.stat()
    return {
        "source": str(path),
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "version": CACHE_VERSION,
    }


def read_steps(visit: str, settings: Settings | None = None) -> pl.DataFrame:
    """Steps for one wave ("06" or "08"): ID, day, minute, steps, sorted."""
    settings = settings or get_settings()
    src = step_file(visit, settings)
    base = settings.work_dir / "cache" / "steps" / f"steps_{visit}"
    parquet, sidecar = base.with_suffix(".parquet"), base.with_suffix(".json")
    meta = _meta(src)
    if parquet.exists() and sidecar.exists() and json.loads(sidecar.read_text()) == meta:
        return pl.read_parquet(parquet)
    out = parse_steps(_read_sas(src), visit)
    parquet.parent.mkdir(parents=True, exist_ok=True)
    # the parquet lands before the sidecar that vouches for it
    with _replacing(parquet) as tmp:
        out.write_parquet(tmp)
    with _replacing(sidecar) as tmp:
        tmp.write_text(json.dumps(meta, indent=1))
    return out
