"""FACT REGISTRY - the verified facts as code (P3, C17's module).

Single source every grader/blocker check reads. Values verified by
Agent 81 against the live store, 2026-10-23. If a number here ever
changes, it changes HERE, once, with the date updated - nowhere else.
"""
from decimal import Decimal

STORE = "shiptrollyard-shop.fourthwall.com"
SINGLE_PRICE = Decimal("19.99")
SINGLE_COMPARE_AT = Decimal("36.99")
BLITZ_END = "Tue Oct 27, 2026"
DUO_PRICE = Decimal("29.99")
DUO_SEPARATELY = Decimal("39.98")     # 2 x 19.99
DUO_COMPARE_AT = Decimal("71.98")     # compare-at total as listed on the duo product
DUO_SAVE_SEPARATELY = Decimal("9.99")   # 39.98 - 29.99
DUO_SAVE_COMPARE = Decimal("41.99")     # 71.98 - 29.99
ALLOWED_SAVINGS = {DUO_SAVE_SEPARATELY, DUO_SAVE_COMPARE}
SIZES = ["S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
SIZE_RANGE_TEXT = "S-5XL"
GARMENT = "Gildan Heavyweight"
TARGET_TOTAL = 156          # a TARGET - never state as live
PROVENANCE = "filmed in Lille, France, 17 Oct 2026"
INTERNAL_ONLY_TERMS = ["profit", "margin", "$10.49", "$10.99", "cost price", "wholesale"]
