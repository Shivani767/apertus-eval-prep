"""Opt-in strict-format math extraction; never replaces historical scoring.

Accepts only a standalone ASCII signed integer/decimal on the last nonempty
line. No prose, units, grouping separators, scientific notation, LaTeX or
locale inference. Rejection means contract not matched, not semantic error.
"""
from decimal import Decimal
import re

PARSER_ID = 'math_last_line_ascii_decimal_v1'
_NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)')


def extract_final_line_number(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or _NUMBER.fullmatch(lines[-1]) is None:
        return None
    # Decimal avoids binary float rounding and preserves large integer values.
    value = Decimal(lines[-1])
    if not value:
        return '0'
    normalized = format(value, 'f')
    return normalized.rstrip('0').rstrip('.') if '.' in normalized else normalized
