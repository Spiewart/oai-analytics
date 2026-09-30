"""Grade a run's metrics against published values (replication studies).

Published values: int = count, float = mean, {or, lo, hi, sig} = odds ratio.
A count replicates within max(3%, 2), a mean within 0.5, and an odds ratio within 0.1
with the same significance. The published `sig` flag is authoritative, because rounded
bounds such as "0.6-1.0" can hide an upper bound below 1.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

import polars as pl

COUNT_REL_TOL = 0.03
COUNT_ABS_TOL = 2
MEAN_TOL = 0.5
OR_TOL = 0.1
EPS = 1e-9
SCHEMA = {
    "metric": pl.String,
    "kind": pl.String,
    "published": pl.String,
    "ours": pl.String,
    "diff": pl.Float64,
    "verdict": pl.String,
    "related": pl.String,
}


def related_for(metric: str, related: Mapping[str, list[str]]) -> list[str]:
    """Assumption keys for the longest prefix of `metric` (matching on dot boundaries)."""
    prefixes = [p for p in related if metric == p or metric.startswith(p + ".")]
    return list(related[max(prefixes, key=len)]) if prefixes else []


def _grade_or(
    pub: Mapping[str, Any], ours: Mapping[str, float], metric: str
) -> tuple[str, str | None, float | None]:
    o, lo, hi = ours.get(metric), ours.get(f"{metric}.lo"), ours.get(f"{metric}.hi")
    if o is None or lo is None or hi is None:
        return "missing", None, None
    sig = hi < 1 or lo > 1
    diff = o - float(pub["or"])
    verdict = "replicated" if abs(diff) <= OR_TOL + EPS and sig == bool(pub["sig"]) else "drift"
    return verdict, f"{o:.2f} ({lo:.2f}-{hi:.2f}){' *' if sig else ''}", diff


def grade(
    published: Mapping[str, Any],
    ours: Mapping[str, float],
    related: Mapping[str, list[str]] | None = None,
    statuses: Mapping[str, str] | None = None,
) -> pl.DataFrame:
    rows = []
    for metric, pub in published.items():
        keys = related_for(metric, related or {})
        related_text = ", ".join(f"{k} ({(statuses or {}).get(k, '?')})" for k in keys)
        if isinstance(pub, Mapping):
            kind = "or"
            pub_text = f"{pub['or']} ({pub['lo']}-{pub['hi']}){' *' if pub['sig'] else ''}"
            verdict, ours_text, diff = _grade_or(pub, ours, metric)
        else:
            kind = "mean" if isinstance(pub, float) else "count"
            pub_text, value = str(pub), ours.get(metric)
            if value is None:
                verdict, ours_text, diff = "missing", None, None
            else:
                diff = float(value) - float(pub)
                tol = MEAN_TOL if kind == "mean" else max(COUNT_REL_TOL * abs(pub), COUNT_ABS_TOL)
                verdict = "replicated" if abs(diff) <= tol + EPS else "drift"
                ours_text = f"{value:.1f}" if kind == "mean" else f"{value:g}"
        rows.append(
            {
                "metric": metric,
                "kind": kind,
                "published": pub_text,
                "ours": ours_text,
                "diff": diff,
                "verdict": verdict,
                "related": related_text,
            }
        )
    return pl.DataFrame(rows, schema=SCHEMA)


def summarize(table: pl.DataFrame, *, section: str, label: str) -> str:
    counts = {
        v: table.filter(pl.col("verdict") == v).height for v in ("replicated", "drift", "missing")
    }
    lines = [
        f"Replication vs published [{section}] (run: {label})",
        " · ".join(f"{n} {v}" for v, n in counts.items()),
    ]
    off = table.filter(pl.col("verdict") != "replicated")
    if off.height:
        lines += ["", "Not replicated:"]
        lines += [
            f"  {r['verdict']:<6} {r['metric']:<42} published {r['published']:<20} ours {r['ours']}"
            for r in off.iter_rows(named=True)
        ]
        implicated = Counter(
            part.split(" (")[0]
            for text in off["related"].to_list()
            if text
            for part in text.split(", ")
        )
        lines += [
            "",
            "Assumptions most implicated: "
            + ", ".join(f"{k} ({n})" for k, n in implicated.most_common(8)),
        ]
    return "\n".join(lines)
