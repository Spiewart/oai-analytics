"""Index of the OAI tables present in a data directory.

File stems end in a two-digit visit code (AllClinical00, kxr_sq_bu06), a cumulative
code (OUTCOMES99, COVIDQ97) or nothing (Enrollees). Names are case-folded, so
kXR_SQ_BU01 and kxr_sq_bu00 are two visits of one table.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from oai.errors import OAIError

CUMULATIVE_CODES = frozenset({"97", "99"})
INPUT_SPEC = re.compile(r"^(?P<table>[a-z0-9_]+)(?::(?P<visit>\d{2}|\*))?$")
_VISIT_SUFFIX = re.compile(r"^(?P<table>.*[^\d])(?P<visit>\d{2})$")

Kind = Literal["visit", "cumulative", "static"]


class CatalogError(OAIError):
    """Unknown table/visit, ambiguous files, or a bad input spec."""


@dataclass(frozen=True)
class TableFile:
    table: str
    visit: str | None
    kind: Kind
    path: Path

    @property
    def key(self) -> str:
        """Stable identifier such as 'allclinical_00' or 'enrollees'."""
        return self.table if self.visit is None else f"{self.table}_{self.visit}"


def parse_filename(path: Path) -> TableFile | None:
    stem = path.stem
    if stem.lower().endswith("_formats"):
        return None
    match = _VISIT_SUFFIX.match(stem)
    if match is None:
        return TableFile(stem.lower(), None, "static", path)
    visit = match["visit"]
    kind: Kind = "cumulative" if visit in CUMULATIVE_CODES else "visit"
    return TableFile(match["table"].lower().rstrip("_"), visit, kind, path)


def _normalize_visit(visit: str | int | None) -> str | None:
    if visit is None:
        return None
    text = str(visit).strip().upper().removeprefix("V")
    if not text.isdigit():
        raise CatalogError(f"Bad visit code {visit!r}")
    return text.zfill(2)


class Catalog:
    def __init__(self, files: Iterable[TableFile]) -> None:
        self._files: dict[tuple[str, str | None], TableFile] = {}
        for tf in files:
            key = (tf.table, tf.visit)
            if key in self._files:
                raise CatalogError(
                    f"Two files map to table {tf.table!r} visit {tf.visit!r}: "
                    f"{self._files[key].path.name} and {tf.path.name}"
                )
            self._files[key] = tf

    @classmethod
    def scan(cls, data_dir: Path) -> Catalog:
        if not data_dir.is_dir():
            raise CatalogError(f"OAI data directory not found: {data_dir}")
        parsed = (parse_filename(p) for p in sorted(data_dir.glob("*.txt")))
        return cls(tf for tf in parsed if tf is not None)

    def __len__(self) -> int:
        return len(self._files)

    def tables(self) -> list[str]:
        return sorted({table for table, _ in self._files})

    def visits(self, table: str) -> list[str]:
        t = table.lower()
        return sorted(v for (name, v) in self._files if name == t and v is not None)

    def get(self, table: str, visit: str | int | None = None) -> TableFile:
        t, v = table.lower(), _normalize_visit(visit)
        try:
            return self._files[(t, v)]
        except KeyError:
            if t not in self.tables():
                raise CatalogError(
                    f"Unknown table {table!r}. Run `oai catalog` to list tables."
                ) from None
            available = ", ".join(self.visits(t)) or "(no visit suffix)"
            raise CatalogError(
                f"Table {t!r} has no visit {visit!r}; available: {available}"
            ) from None

    def resolve_input(self, spec: str) -> list[TableFile]:
        match = INPUT_SPEC.match(spec)
        if match is None:
            raise CatalogError(f"Bad input spec {spec!r}; use 'table', 'table:VV' or 'table:*'")
        table, visit = match["table"], match["visit"]
        if visit == "*":
            files = [self._files[(table, v)] for v in self.visits(table)]
            if not files:
                raise CatalogError(f"No visits found for table {table!r}")
            return files
        return [self.get(table, visit)]


@lru_cache(maxsize=4)
def catalog_for(data_dir: Path) -> Catalog:
    """Cached catalog per data directory."""
    return Catalog.scan(data_dir)
