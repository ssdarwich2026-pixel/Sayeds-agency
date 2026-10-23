"""PACKET VALIDATION (P4 - C27's module).

A listing packet is the ONLY thing the Listing Executor may create
from: copy-exact, never composed. Validation is strict on the
economics and the geometry because Wave 1's failures were invented
numbers. A packet that fails validation is refused by name, never
"fixed up" by the executor.

Verified shape (from the 113 built packets, 2026-10-23):
title_exact, print_file (must exist), price $19.99, compare-at
$36.99, sizes S-5XL, a default colour, a placement rule.
"""
from dataclasses import dataclass, field
from decimal import Decimal

EXPECTED_PRICE = Decimal("19.99")
EXPECTED_COMPARE = Decimal("36.99")
EXPECTED_SIZES = "S-5XL"


@dataclass
class Packet:
    key: str                 # ledger key (print_file path)
    title: str
    print_file: str
    price: Decimal = EXPECTED_PRICE
    compare_at: Decimal = EXPECTED_COMPARE
    sizes: str = EXPECTED_SIZES
    default_colour: str = "Black"
    placement: str = ""
    provenance: str = ""


def validate_packet(packet, file_exists):
    """-> list of errors (empty = valid). file_exists is injected so
    the cage test uses a fake filesystem and the Pitch lane passes
    the real os.path.exists."""
    errors = []
    if not packet.title or not packet.title.strip():
        errors.append("title is empty")
    if not packet.print_file:
        errors.append("print_file is empty")
    elif not file_exists(packet.print_file):
        errors.append(f"print_file does not exist: {packet.print_file}")
    if packet.price != EXPECTED_PRICE:
        errors.append(f"price {packet.price} != verified {EXPECTED_PRICE}")
    if packet.compare_at != EXPECTED_COMPARE:
        errors.append(f"compare_at {packet.compare_at} != verified {EXPECTED_COMPARE}")
    if packet.sizes != EXPECTED_SIZES:
        errors.append(f"sizes {packet.sizes!r} != verified {EXPECTED_SIZES!r}")
    if not packet.default_colour:
        errors.append("default_colour is empty")
    if not packet.placement:
        errors.append("placement rule is empty")
    return errors
