"""A load failure must name its cause, not hide it behind a generic message.

A gated repository returns 401, a wrong revision and a missing optional package all
produced the identical string "local model/tokenizer could not be loaded", so a real
Colab run failed on all 257 examples with no diagnosis. The detail now travels with the
error, redacted and bounded, because the message is written into run artifacts.
"""
from __future__ import annotations

from apertus_eval_prep.adapters.local_transformers import load_error_detail


def test_gated_repository_cause_is_named():
    gated = OSError(
        "You are trying to access a gated repo. Make sure you have access to it at "
        "https://huggingface.co/google/gemma-2-2b-it.\n401 Client Error"
    )
    detail = load_error_detail(gated)
    assert "OSError" in detail
    assert "gated repo" in detail
    assert "401" in detail


def test_credentials_in_the_cause_are_redacted():
    """Credential shapes are redacted; the artifact policy deliberately leaves other PII.

    ``redact_text_for_artifact`` uses the artifact policy (credential, credential
    assignment, URL credentials), so a token disappears from the error while a plain
    email address is kept, exactly as it is kept in every other artifact.
    """
    leaky = OSError("hf_abcdefghij0123456789ABCDEFGHIJ0123 failed for person@example.com")
    detail = load_error_detail(leaky)
    assert "hf_abcdefghij0123456789ABCDEFGHIJ0123" not in detail
    assert "[REDACTED:credential]" in detail
    assert "person@example.com" in detail  # artifact policy is credential-only, by design


def test_detail_is_bounded_and_single_line():
    detail = load_error_detail(ValueError("x " * 5000), limit=120)
    assert len(detail) <= 120
    assert "\n" not in detail
