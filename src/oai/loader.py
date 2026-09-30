"""Load OAI pipe-delimited tables as typed polars frames, via a Parquet cache.

Raw OAI cells look like "1: Right" (code + label), "2" (plain value) or
".: Missing Form/Incomplete Workbook" (missing-value code). Parsing keeps the code as
the cell value, moves labels into a per-table Codebook, resolves missing codes with
resolve_missing(), and casts a column to Int64/Float64 when every value allows it.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from oai.catalog import TableFile, catalog_for
from oai.config import Settings, get_settings

CODED = r"^(-?\d+(?:\.\d+)?): (.*)$"
MISSING = r"^\.[A-Z]?(?:: .*)?$"
MISSING_CODE = r"^(\.[A-Z]?)"
MISSING_LABEL = r"^\.[A-Z]?: (.*)$"
LEADING_ZERO = r"^-?0\d"
# sink_parquet streams tall/narrow tables (accelerometer minutes) efficiently but is
# pathologically slow on wide ones (AllClinical: ~1,200 columns), so pick by width.
STREAMING_MAX_COLUMNS = 64
# Bump when parsing rules change so existing caches are rebuilt.
PARSER_VERSION = 1


def resolve_missing(raw: str) -> str | None:
    """Decide what a missing-value cell becomes. USER-AUTHORED POLICY.

    `raw` is the whole cell, e.g. ".: Missing Form/Incomplete Workbook" or
    ".A: Not Expected". The return value replaces the cell before type inference;
    the code and label are always kept in Codebook.missing for that column.

    - Return None for everything: clean numeric columns; the per-cell reason is lost
      (the codebook still lists which reasons occur in each column).
    - Return a sentinel for some codes (e.g. keep ".A" distinct): any non-numeric
      sentinel turns that entire column into strings.

    Editing this function invalidates every cached table (see policy_fingerprint).
    """
    return None


@dataclass
class Codebook:
    labels: dict[str, dict[str, str]] = field(default_factory=dict)
    missing: dict[str, dict[str, str]] = field(default_factory=dict)

    def to_json(self) -> dict[str, dict[str, dict[str, str]]]:
        return {"labels": self.labels, "missing": self.missing}

    @classmethod
    def from_json(cls, data: dict) -> Codebook:
        return cls(labels=data["labels"], missing=data["missing"])


def policy_fingerprint() -> str:
    """Changes whenever the parser version or the resolve_missing source changes."""
    source = inspect.getsource(resolve_missing)
    return hashlib.sha256(f"{PARSER_VERSION}\n{source}".encode()).hexdigest()[:16]


def _scan_text(path: Path) -> pl.LazyFrame:
    return pl.scan_csv(
        path, separator="|", infer_schema=False, quote_char=None, encoding="utf8-lossy"
    )


def parse_table(path: Path) -> tuple[pl.LazyFrame, Codebook]:
    """Lazy frame with coded cells split, missing codes resolved and numerics cast."""
    lf = _scan_text(path)
    columns = lf.collect_schema().names()

    raw_missing = (
        lf.select(
            [pl.col(c).filter(pl.col(c).str.contains(MISSING)).unique().implode() for c in columns]
        )
        .collect()
        .row(0)
    )
    replacements = {raw: resolve_missing(raw) for values in raw_missing for raw in values}

    def cleaned(c: str) -> pl.Expr:
        col = pl.col(c)
        if not replacements:
            return col
        return (
            pl.when(col.str.contains(MISSING))
            .then(col.replace_strict(replacements, default=None, return_dtype=pl.String))
            .otherwise(col)
        )

    def value(c: str) -> pl.Expr:
        col = cleaned(c)
        return pl.coalesce(col.str.extract(CODED, 1), col)

    stats_exprs: list[pl.Expr] = []
    for c in columns:
        v, raw = value(c), pl.col(c)
        present = v.is_not_null()
        stats_exprs += [
            (present & v.str.to_integer(strict=False).is_null()).sum().alias(f"{c}::notint"),
            (present & v.cast(pl.Float64, strict=False).is_null()).sum().alias(f"{c}::notfloat"),
            (present & v.str.contains(LEADING_ZERO)).sum().alias(f"{c}::lead0"),
            pl.struct(code=raw.str.extract(CODED, 1), label=raw.str.extract(CODED, 2))
            .filter(raw.str.contains(CODED))
            .unique()
            .implode()
            .alias(f"{c}::labels"),
            pl.struct(
                code=raw.str.extract(MISSING_CODE, 1), label=raw.str.extract(MISSING_LABEL, 1)
            )
            .filter(raw.str.contains(MISSING))
            .unique()
            .implode()
            .alias(f"{c}::missing"),
        ]
    stats = lf.select(stats_exprs).collect().row(0, named=True)

    book = Codebook()
    typed: list[pl.Expr] = []
    for c in columns:
        v = value(c)
        if stats[f"{c}::lead0"] == 0:
            if stats[f"{c}::notint"] == 0:
                v = v.cast(pl.Int64)
            elif stats[f"{c}::notfloat"] == 0:
                v = v.cast(pl.Float64)
        typed.append(v.alias(c))
        if labels := stats[f"{c}::labels"]:
            ordered = sorted(labels, key=lambda d: float(d["code"]))
            book.labels[c] = {d["code"]: d["label"] for d in ordered}
        if missing := stats[f"{c}::missing"]:
            book.missing[c] = {d["code"]: d["label"] or "" for d in missing}
    return lf.select(typed), book


def _source_meta(path: Path) -> dict[str, object]:
    st = path.stat()
    return {
        "source": str(path),
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "policy": policy_fingerprint(),
    }


def ensure_cached(tf: TableFile, settings: Settings) -> tuple[Path, Codebook]:
    """Return (parquet path, codebook), rebuilding the cache when it is stale."""
    base = settings.work_dir / "cache" / tf.key
    parquet, sidecar = base.with_suffix(".parquet"), base.with_suffix(".json")
    meta = _source_meta(tf.path)
    if parquet.exists() and sidecar.exists():
        stored = json.loads(sidecar.read_text())
        if stored.get("meta") == meta:
            return parquet, Codebook.from_json(stored["codebook"])
    parquet.parent.mkdir(parents=True, exist_ok=True)
    lf, book = parse_table(tf.path)
    tmp = parquet.parent / f"{parquet.name}.tmp"
    if len(lf.collect_schema()) <= STREAMING_MAX_COLUMNS:
        lf.sink_parquet(tmp)
    else:
        lf.collect().write_parquet(tmp)
    tmp.replace(parquet)
    sidecar.write_text(json.dumps({"meta": meta, "codebook": book.to_json()}, indent=1))
    return parquet, book


def _table_file(name: str, visit: str | int | None, settings: Settings) -> TableFile:
    return catalog_for(settings.data_dir).get(name, visit)


def read_table(
    name: str,
    visit: str | int | None = None,
    *,
    columns: list[str] | None = None,
    lazy: bool = False,
    settings: Settings | None = None,
) -> pl.DataFrame | pl.LazyFrame:
    """Load an OAI table, e.g. read_table("kxr_sq_bu", "00", columns=["ID", "SIDE"])."""
    settings = settings or get_settings()
    parquet, _ = ensure_cached(_table_file(name, visit, settings), settings)
    if lazy:
        lf = pl.scan_parquet(parquet)
        return lf.select(columns) if columns else lf
    return pl.read_parquet(parquet, columns=columns)


def codebook(
    name: str, visit: str | int | None = None, *, settings: Settings | None = None
) -> Codebook:
    """Value labels and missing-value codes for a table."""
    settings = settings or get_settings()
    return ensure_cached(_table_file(name, visit, settings), settings)[1]
