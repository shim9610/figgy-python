"""Read NIST ASD CSV exports without evaluating spreadsheet expressions."""

import csv
from dataclasses import dataclass, field
import io
import math
from numbers import Real
from pathlib import Path
import re


@dataclass
class NistData:
    levels: list
    transitions: list = field(default_factory=list)
    limits: list = field(default_factory=list)
    energy_unit: str = ""
    wavelength_unit: str = ""
    wavelength_medium: str = ""
    unmatched_transitions: int = 0


def _text(value):
    if value is None or (isinstance(value, Real) and math.isnan(value)):
        return ""
    value = str(value).strip()
    return value[2:-1] if value.startswith('="') and value.endswith('"') else value


def _table(source):
    if hasattr(source, "to_dict"):
        rows = source.to_dict("records")
    elif hasattr(source, "read"):
        rows = csv.DictReader(source)
    elif isinstance(source, (str, Path)):
        text = str(source)
        if "\n" not in text:
            text = Path(source).read_text(encoding="utf-8-sig")
        rows = csv.DictReader(io.StringIO(text))
    else:
        rows = source
    return [
        {
            str(k).strip().lstrip("\ufeff"): _text(v)
            for k, v in row.items()
            if k is not None
        }
        for row in rows
    ]


def _number(value):
    value = _text(value)
    if not value:
        return None
    match = re.fullmatch(
        r"[\[(]?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*[\])]?(?:\?|\+x)?",
        value,
    )
    if match is None:
        raise ValueError("unrecognized NIST numeric field: " + value)
    return float(match.group(1))


def _id(configuration, term, j):
    return " | ".join((configuration, term, j))


def read_nist(levels, lines=None, *, unmatched="raise", wavelength="observed"):
    """Read exported CSV paths, text, streams or tables for ``ax.energy_levels``.

    Preserve source units and qualifiers. ``wavelength`` chooses observed values
    with Ritz fallback, or Ritz values with observed fallback. No unit conversion
    or selection-rule inference is performed. Unmatched transitions are rejected
    unless the caller explicitly chooses ``unmatched='skip'``.
    """
    if unmatched not in ("raise", "skip") or wavelength not in ("observed", "ritz"):
        raise ValueError("unmatched is raise/skip; wavelength is observed/ritz")
    rows = _table(levels)
    if not rows:
        raise ValueError("NIST levels table is empty")
    energy_key = next(
        (key for key in rows[0] if re.fullmatch(r"Level \(.+\)", key)), None
    )
    if energy_key is None:
        raise ValueError("NIST levels table requires a Level (unit) column")
    missing = {"Configuration", "Term", "J"} - rows[0].keys()
    if missing:
        raise ValueError("missing NIST levels columns: " + ", ".join(sorted(missing)))
    unit = energy_key[len("Level (") : -1]
    out = NistData([], energy_unit=unit)
    uncertainty_key = "Uncertainty (" + unit + ")"
    ids = set()
    for row in rows:
        energy = _number(row[energy_key])
        if energy is None:
            continue
        ident = _id(row["Configuration"], row["Term"], row["J"])
        if ident in ids:
            raise ValueError("ambiguous duplicate NIST level: " + ident)
        ids.add(ident)
        item = dict(
            id=ident,
            energy=energy,
            uncertainty=_number(row.get(uncertainty_key)),
            reference=row.get("Reference", ""),
        )
        if row["Term"] == "Limit":
            item["label"] = row["Configuration"]
            out.limits.append(item)
        else:
            item.update(
                column=row["Term"] or row["Configuration"],
                configuration=row["Configuration"],
                term=row["Term"],
                j=row["J"],
                g=_number(row.get("g")),
                prefix=row.get("Prefix", ""),
                suffix=row.get("Suffix", ""),
            )
            out.levels.append(item)
    if not out.levels:
        raise ValueError("NIST table contains no numeric energy levels")
    if lines is None:
        return out
    line_rows = _table(lines)
    if not line_rows:
        return out
    required = {"conf_i", "term_i", "J_i", "conf_k", "term_k", "J_k"}
    missing = required - line_rows[0].keys()
    if missing:
        raise ValueError("missing NIST lines columns: " + ", ".join(sorted(missing)))
    keys = line_rows[0].keys()
    observed = next((key for key in keys if key.startswith("obs_wl_")), None)
    ritz = next((key for key in keys if key.startswith("ritz_wl_")), None)
    if observed and ritz and observed[len("obs_wl_") :] != ritz[len("ritz_wl_") :]:
        raise ValueError(
            "observed and Ritz wavelengths must use the same medium and unit"
        )
    chosen = observed or ritz
    if chosen:
        match = re.search(r"_(air|vac)\((.+)\)", chosen)
        if match:
            out.wavelength_medium, out.wavelength_unit = match.groups()
    level_ids = {item["id"] for item in out.levels}
    for index, row in enumerate(line_rows):
        lower = _id(*(row[key] for key in ("conf_i", "term_i", "J_i")))
        upper = _id(*(row[key] for key in ("conf_k", "term_k", "J_k")))
        if lower not in level_ids or upper not in level_ids:
            if unmatched == "raise":
                raise ValueError(
                    "NIST line names a level absent from the levels table: "
                    + lower
                    + " -> "
                    + upper
                )
            out.unmatched_transitions += 1
            continue
        primary, fallback = (
            (observed, ritz) if wavelength == "observed" else (ritz, observed)
        )
        primary_value = _number(row.get(primary))
        use_primary = primary_value is not None
        wl = primary_value if use_primary else _number(row.get(fallback))
        uncertainty = (
            "unc_obs_wl"
            if (primary if use_primary else fallback) == observed
            else "unc_ritz_wl"
        )
        out.transitions.append(
            dict(
                id=f"line_{index}",
                lower=lower,
                upper=upper,
                wavelength=wl,
                wavelength_uncertainty=_number(row.get(uncertainty)),
                intensity=row.get("intens", ""),
                aki=_number(row.get("Aki(s^-1)")),
                accuracy=row.get("Acc", ""),
                line_type=row.get("Type", ""),
                tp_reference=row.get("tp_ref", ""),
                line_reference=row.get("line_ref", ""),
            )
        )
    return out
