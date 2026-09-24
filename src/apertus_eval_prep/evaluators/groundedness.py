"""Heuristic groundedness evaluation for offline fixtures."""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", str(text).lower()) if len(token) > 2}


def groundedness_score(answer: str, contexts: Iterable[Mapping[str, Any]], *, threshold: float = 0.35) -> dict[str, Any]:
    """Measure lexical support for an answer against supplied context.

    This is an auditable offline heuristic, not a semantic or human judgment.
    """
    context_items = list(contexts)
    supported = set()
    for item in context_items:
        supported.update(_tokens(str(item.get("content", ""))))
    answer_tokens = _tokens(answer)
    if not answer_tokens:
        return {"score": 0.0, "supported_token_fraction": 0.0, "unsupported_claim_rate": 1.0,
                "method": "lexical_overlap_heuristic", "uncertainty": "empty answer"}
    overlap = len(answer_tokens & supported) / len(answer_tokens)
    return {"score": overlap, "supported_token_fraction": overlap,
            "unsupported_claim_rate": max(0.0, 1.0 - overlap),
            "supported": overlap >= threshold, "method": "lexical_overlap_heuristic",
            "threshold": threshold, "uncertainty": "semantic equivalence and citation quality are not assessed"}


def citation_support(
    answer: str, contexts: Iterable[Mapping[str, Any]], expected_sources: Iterable[str] = ()
) -> dict[str, Any]:
    source_ids = {str(item.get("source_id")) for item in contexts if item.get("source_id")}
    cited = {token.strip("[]()") for token in re.findall(r"\[([^\]]+)\]", answer)}
    expected = {str(item) for item in expected_sources if str(item)}
    known = cited & source_ids
    supported_expected = expected & known if expected else known
    return {
        "citation_count": len(cited),
        "known_citations": sorted(known),
        "unknown_citations": sorted(cited - source_ids),
        "expected_sources": sorted(expected),
        "supported_expected_sources": sorted(supported_expected),
        "expected_source_coverage": (len(supported_expected) / len(expected)) if expected else None,
        "citation_precision": (len(known) / len(cited)) if cited else None,
        "method": "explicit_bracket_citations",
    }


__all__ = ["groundedness_score", "citation_support"]
