"""Dependency-free HTML building blocks for static reports.

The reports are opened locally, in a browser, or inside GitHub, so they must render as
HTML rather than as escaped Markdown in a ``<pre>`` block. Every value goes through
:func:`cell`, which formats numbers readably, JSON-encodes containers, and marks missing
values explicitly instead of printing ``None``. All text is escaped, and report text is
still passed through the PII redactor.
"""
from __future__ import annotations

import html
import json
from typing import Any, Iterable, Mapping, Sequence

from apertus_eval_prep.utils.pii import redact_text_for_report

#: Shared stylesheet. Deliberately small: no fonts, scripts or network requests.
CSS = (
    "body{font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:1100px;margin:2rem auto;"
    "padding:0 1rem;color:#172033;background:#f7f9fc}"
    "header{margin-bottom:1rem}h1{font-size:1.6rem;margin:0 0 .5rem}"
    "section{background:#fff;border:1px solid #dbe2ea;border-radius:8px;padding:1rem 1.2rem;margin:1rem 0}"
    "h2{font-size:1.15rem;margin:0 0 .6rem}h3{font-size:1rem;margin:.8rem 0 .4rem}"
    ".badge{background:#fff1bf;border:1px solid #d7ae2a;border-radius:6px;padding:.4rem .6rem;font-weight:600}"
    ".cards{display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0}"
    ".card{background:#eef5ff;border:1px solid #c8dcf7;border-radius:8px;padding:.55rem .8rem;min-width:9rem}"
    ".card b{display:block;font-size:.78rem;color:#41536b;text-transform:uppercase;letter-spacing:.02em}"
    ".card strong{display:block;font-size:1.1rem}"
    "table{border-collapse:collapse;width:100%;margin:.4rem 0}"
    "th,td{border:1px solid #dbe2ea;padding:.4rem .5rem;text-align:left;vertical-align:top}"
    "th{background:#eef2f7}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}"
    "code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.85em}"
    "pre{white-space:pre-wrap;overflow:auto;background:#101827;color:#d7e2f0;padding:.8rem;border-radius:6px}"
    "ul{margin:.3rem 0;padding-left:1.2rem}.note{color:#41536b}.warn{color:#8a5a00;font-weight:600}"
    "details{margin:.35rem 0}summary{cursor:pointer}"
)

#: Longest container value rendered inline before it is truncated with a marker.
MAX_INLINE_CHARS = 400

def escape(value: Any) -> str:
    """Escape a value for an HTML text node after redacting report text.

    Quotes are left alone on purpose: these values are text content, never attribute
    values, and escaping them as ``&quot;`` only makes the saved HTML harder to read.
    """
    return html.escape(redact_text_for_report(str(value if value is not None else "")), quote=False)


def number(value: float) -> str:
    """Format a float for reading: 4 decimals for scores, grouped for large values."""
    if value != value or value in (float("inf"), float("-inf")):  # NaN / inf are not evidence
        return "unavailable"
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    if value != 0.0 and abs(value) < 0.0001:
        return f"{value:.2e}"
    return f"{value:.4f}"


def cell(value: Any) -> str:
    """Format one report value: explicit for missing data, readable for containers."""
    if value is None:
        return "unavailable"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return number(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (Mapping, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, default=str, sort_keys=isinstance(value, Mapping))
        if len(text) > MAX_INLINE_CHARS:
            text = text[: MAX_INLINE_CHARS - 1] + "…"
        return text
    return str(value)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def page(title: str, body: str, *, badge: str = "") -> str:
    """Wrap report content in a complete, self-contained HTML document."""
    header = f"<header><h1>{escape(title)}</h1>"
    if badge:
        header += f"<div class='badge'>{escape(badge)}</div>"
    header += "</header>"
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width'>"
        f"<title>{escape(title)}</title><style>{CSS}</style></head><body>{header}{body}</body></html>\n"
    )


def section(title: str, body: str) -> str:
    """One titled report section."""
    return f"<section><h2>{escape(title)}</h2>{body}</section>"


def cards(pairs: Sequence[tuple[str, Any]]) -> str:
    """Headline metric cards."""
    inner = "".join(
        f"<div class='card'><b>{escape(name)}</b><strong>{escape(cell(value))}</strong></div>" for name, value in pairs
    )
    return f"<div class='cards'>{inner}</div>"


def table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """A data table; numeric-looking cells are right aligned."""
    head = "".join(f"<th>{escape(name)}</th>" for name in headers)
    body_rows = []
    for row in rows:
        cells = "".join(
            f"<td class='num'>{escape(cell(value))}</td>" if _is_number(value) else f"<td>{escape(cell(value))}</td>"
            for value in row
        )
        body_rows.append(f"<tr>{cells}</tr>")
    if not body_rows:
        body_rows.append(f"<tr><td colspan='{len(headers)}' class='note'>unavailable / insufficient evidence</td></tr>")
    return f"<table><tr>{head}</tr>{''.join(body_rows)}</table>"


def key_values(pairs: Iterable[tuple[str, Any]]) -> str:
    """A two-column field/value table."""
    return table(["Field", "Value"], [[name, value] for name, value in pairs])


def bullets(items: Iterable[Any]) -> str:
    """An unordered list, or an explicit empty state."""
    rendered = "".join(f"<li>{escape(cell(item))}</li>" for item in items)
    return f"<ul>{rendered}</ul>" if rendered else "<p class='note'>None identified.</p>"


def paragraph(text: Any, *, css_class: str = "note") -> str:
    """A single note paragraph."""
    return f"<p class='{css_class}'>{escape(text)}</p>"


def pre_block(text: Any) -> str:
    """A monospace block for commands and raw payloads (not prose)."""
    return f"<pre>{escape(text)}</pre>"


def details(summary: str, body: str) -> str:
    """A collapsed block, used for raw per-example payloads."""
    return f"<details><summary>{escape(summary)}</summary>{body}</details>"


__all__ = [
    "CSS", "bullets", "cards", "cell", "details", "escape", "key_values",
    "number", "page", "paragraph", "pre_block", "section", "table",
]
