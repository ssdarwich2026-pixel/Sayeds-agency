"""MANIFEST PARSER (P1 - completes the manifest binding TODO).

Binds the two real manifest dialects the launch already uses to the
ledger, so P1 is driven by files, not by hand-typed entries:

- packets CSV (blitz-listing packets-remaining.csv): every row is a
  BUILT packet -> the entry enters at PACKET READY. Columns include
  drain_order, group, title_exact, print_file, print_file_exists,
  price_usd, compare_at_usd, sizes, status.
- drain CSV (list-all-154-drain-*.csv): the master target list ->
  entries enter at NOT STARTED. Columns include group, name,
  print_file, provenance, status.

Keys are print_file paths (unique per design). A row with no
print_file is skipped and named in the returned warnings - never
silently dropped, never invented. A duplicate print_file raises
LedgerError via Ledger.add. Stdlib only.
"""
import csv
import io
from pathlib import Path

from ledger import Ledger

EV_SOURCE = "manifest"


def _evidence(value):
    return {"source": EV_SOURCE, "ts": 0, "value": value}


def parse_rows(text):
    """CSV text -> (rows, dialect). Dialect is 'packets' or 'drain'."""
    reader = csv.DictReader(io.StringIO(text))
    fields = set(reader.fieldnames or [])
    if "title_exact" in fields:
        dialect = "packets"
    elif "name" in fields and "print_file" in fields:
        dialect = "drain"
    else:
        raise ValueError(f"unrecognised manifest dialect, columns: {sorted(fields)}")
    return list(reader), dialect


def build_ledger(text):
    """CSV text -> (Ledger, warnings). Packets rows land PACKET READY;
    drain rows land NOT STARTED."""
    rows, dialect = parse_rows(text)
    ledger = Ledger()
    warnings = []
    for i, row in enumerate(rows, start=2):  # line 1 is the header
        print_file = (row.get("print_file") or "").strip()
        title = (row.get("title_exact") or row.get("name") or "").strip()
        if not print_file:
            warnings.append(f"line {i}: skipped, no print_file (title={title!r})")
            continue
        if dialect == "packets" and (row.get("print_file_exists") or "").strip().lower() == "false":
            warnings.append(f"line {i}: {print_file} flagged print_file_exists=False, still loaded")
        ledger.add(print_file, title, print_file)
        if dialect == "packets":
            ledger.transition(print_file, "PACKET READY", _evidence(f"packets line {i}"))
    return ledger, warnings


def load_ledger(path):
    """Path -> (Ledger, warnings)."""
    return build_ledger(Path(path).read_text())
