"""Load OAI pipe-delimited tables as typed polars frames, via a Parquet cache.

Raw OAI cells look like "1: Right" (code + label), "2" (plain value), " " (blank) or
".: Missing Form/Incomplete Workbook" (missing-value code). Parsing trims blanks to
null, keeps the code as the cell value, moves labels into a per-table Codebook,
resolves missing codes with resolve_missing(), and casts a column to Int64/Float64
when every value allows it. Records split by newlines inside a field are rejoined.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from oai.catalog import TableFile, catalog_for
from oai.config import Settings, get_settings
from oai.errors import OAIError

CODED = r"^(-?\d+(?:\.\d+)?): (.*)$"
MISSING = r"^\.[A-Z]?(?:: .*)?$"
MISSING_CODE = r"^(\.[A-Z]?)"
MISSING_LABEL = r"^\.[A-Z]?: (.*)$"
LEADING_ZERO = r"^-?0\d"
REASON_SUFFIX = "__reason"
SEPARATORS = ("|", ",")  # OAI tables are pipe-delimited; a few (hxr_sq_summary) are CSV
# polars' streaming engine bounds memory on tall/narrow tables (accelerometer minutes)
# but is pathologically slow and memory-hungry on wide ones (AllClinical: ~1,200
# columns: 65 s / 15 GB vs 5 s in memory), so every pass picks its engine by width.
STREAMING_MAX_COLUMNS = 64
# Bump when parsing rules change (the whole loader.py source is fingerprinted too).
PARSER_VERSION = 2


class LoaderError(OAIError):
    """A table file could not be parsed faithfully."""


@dataclass(frozen=True)
class MissingResolution:
    """What a missing-value cell becomes.

    `value` replaces the cell (None = null); a non-None `reason` is written to a
    `<column>__reason` sidecar column next to the value column.
    """

    value: str | None = None
    reason: str | None = None


def resolve_missing(raw: str, *, column: str, table: str) -> MissingResolution:
    """Decide what a missing-value cell becomes. USER-AUTHORED POLICY.

    `raw` is the whole cell, e.g. ".: Missing Form/Incomplete Workbook", ".A: Not
    Expected" or ".P: Prosthetic"; `column` and `table` (e.g. "V06XRKL", "kxr_sq_bu_06")
    allow column-aware rules. Codes seen in the release: "." missing form, .M missing,
    .A not expected, .N not required, .T technical problems, .F phone contact, .X don't do,
    .R refused, .J unassigned, .P prosthetic, .D don't know.

    - MissingResolution() -> null cell, no sidecar (the codebook still lists the codes).
    - MissingResolution(reason=...) -> null cell plus the reason in <column>__reason,
      e.g. to keep ".P" (replaced knee) distinguishable for progression endpoints.
    - MissingResolution(value=...) -> a sentinel; a non-numeric one makes the column String.

    Keep any helpers in this module: editing loader.py rebuilds every cached table.
    """
    return MissingResolution()


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
    """Changes whenever loader.py (parser + missing policy) or the polars version changes."""
    extra = f"\n{PARSER_VERSION}\n{pl.__version__}".encode()
    return hashlib.sha256(Path(__file__).read_bytes() + extra).hexdigest()[:16]


def _read_header(path: Path) -> str:
    with path.open("rb") as fh:
        return fh.readline().decode("utf-8", errors="replace").rstrip("\r\n")


def _has_misaligned_lines(path: Path, expected: int) -> bool:
    """True when any line has a different number of '|' separators than the header."""
    lines = pl.scan_csv(
        path,
        has_header=False,
        separator="\x1f",
        quote_char=None,
        new_columns=["line"],
        infer_schema=False,
        encoding="utf8-lossy",
    )
    mismatch = pl.col("line").str.count_matches("|", literal=True) != expected
    return bool(lines.select(mismatch.any()).collect(engine="streaming").item())


def _rejoin_records(path: Path, expected: int) -> bytes:
    """Rejoin records split by newlines inside a field; raise when counts can't reconcile."""
    lines = re.split(r"\r?\n", path.read_bytes().decode("utf-8", errors="replace").rstrip("\r\n"))
    out, buf, start = [lines[0]], None, 0
    for number, line in enumerate(lines[1:], start=2):
        buf, start = (line, number) if buf is None else (f"{buf} {line}", start)
        count = buf.count("|")
        if count == expected:
            out.append(buf)
            buf = None
        elif count > expected:
            raise LoaderError(
                f"{path.name}: line {start}: {count + 1} fields, expected {expected + 1}"
            )
    if buf is not None:
        raise LoaderError(
            f"{path.name}: line {start}: record ends early ({buf.count('|') + 1} of {expected + 1} fields)"
        )
    return ("\n".join(out) + "\n").encode()


def _scan_text(path: Path) -> pl.LazyFrame:
    header = _read_header(path)
    separator = next((s for s in SEPARATORS if s in header), None)
    if separator is None:
        raise LoaderError(f"{path.name}: header has no '|' or ',' separator; not a delimited table")
    if separator == ",":
        return pl.scan_csv(path, separator=",", infer_schema=False, encoding="utf8-lossy")
    expected = header.count("|")
    if _has_misaligned_lines(path, expected):
        data = _rejoin_records(path, expected)
        return pl.read_csv(
            io.BytesIO(data), separator="|", infer_schema=False, quote_char=None
        ).lazy()
    return pl.scan_csv(
        path, separator="|", infer_schema=False, quote_char=None, encoding="utf8-lossy"
    )


def parse_table(path: Path, *, table: str | None = None) -> tuple[pl.LazyFrame, Codebook]:
    """Lazy frame with blanks nulled, coded cells split, missing codes resolved, numerics cast."""
    table = table or path.stem.lower()
    lf = _scan_text(path)
    columns = lf.collect_schema().names()
    # Streaming bounds memory on tall/narrow tables but is pathological on wide ones.
    engine = "streaming" if len(columns) <= STREAMING_MAX_COLUMNS else "in-memory"

    # Trim once and turn blank cells (the release uses " ") into nulls; wide tables are
    # few rows, so materialize them rather than re-evaluating the trim in every pass.
    stripped = [pl.col(c).str.strip_chars() for c in columns]
    lf = lf.with_columns(
        [
            pl.when(s == "").then(None).otherwise(s).alias(c)
            for s, c in zip(stripped, columns, strict=True)
        ]
    )
    if engine == "in-memory":
        lf = lf.collect().lazy()

    def raw(c: str) -> pl.Expr:
        return pl.col(c)

    raw_missing = (
        lf.select(
            [
                raw(c).filter(raw(c).str.contains(MISSING)).unique().implode().alias(c)
                for c in columns
            ]
        )
        .collect(engine=engine)
        .row(0, named=True)
    )
    resolutions = {
        c: {m: resolve_missing(m, column=c, table=table) for m in values}
        for c, values in raw_missing.items()
        if values
    }

    def cleaned(c: str) -> pl.Expr:
        col, res = raw(c), resolutions.get(c)
        if not res:
            return col
        values = {m: r.value for m, r in res.items()}
        return (
            pl.when(col.str.contains(MISSING))
            .then(col.replace_strict(values, default=None, return_dtype=pl.String))
            .otherwise(col)
        )

    def reason(c: str) -> pl.Expr | None:
        reasons = {m: r.reason for m, r in resolutions.get(c, {}).items() if r.reason is not None}
        if not reasons:
            return None
        return (
            raw(c)
            .replace_strict(reasons, default=None, return_dtype=pl.String)
            .alias(f"{c}{REASON_SUFFIX}")
        )

    def value(c: str) -> pl.Expr:
        col = cleaned(c)
        return pl.coalesce(col.str.extract(CODED, 1), col)

    stats_exprs: list[pl.Expr] = []
    for c in columns:
        v, r = value(c), raw(c)
        present = v.is_not_null()
        stats_exprs += [
            (present & v.str.to_integer(strict=False).is_null()).sum().alias(f"{c}::notint"),
            (present & v.cast(pl.Float64, strict=False).is_null()).sum().alias(f"{c}::notfloat"),
            (present & v.str.contains(LEADING_ZERO)).sum().alias(f"{c}::lead0"),
            pl.struct(code=r.str.extract(CODED, 1), label=r.str.extract(CODED, 2))
            .filter(r.str.contains(CODED))
            .unique()
            .implode()
            .alias(f"{c}::labels"),
            pl.struct(code=r.str.extract(MISSING_CODE, 1), label=r.str.extract(MISSING_LABEL, 1))
            .filter(r.str.contains(MISSING))
            .unique()
            .implode()
            .alias(f"{c}::missing"),
        ]
    stats = lf.select(stats_exprs).collect(engine=engine).row(0, named=True)

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
        if (reason_expr := reason(c)) is not None:
            typed.append(reason_expr)
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
    lf, book = parse_table(tf.path, table=tf.key)
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
