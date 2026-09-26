"""A gated model must be caught by the preflight, not by 257 adapter failures.

A real Colab run of google/gemma-2-2b-it scored 0 of 257 examples: the notebook
printed "model access OK" and then every weight download returned 401. Two causes
are pinned here, because both are silent by construction:

* gated repositories publish their metadata, so a metadata check passes with no
  credential at all while the download fails;
* an ambient token was accepted without being validated, so a revoked or expired
  token looked like a working one and shadowed the freshly rotated secret.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest

from apertus_eval_prep import hub_auth
from apertus_eval_prep.hub_auth import HubAccessError, check_model_access, resolve_hub_token

SECRET = "hf_" + "s" * 36
STALE = "hf_" + "x" * 36


@dataclass
class FakeInfo:
    sha: str = "0cb88a4f764b7a12671c53f0838cd831a0843b95"
    gated: str | None = "auto"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """No token, no secret, and no on-disk token unless a test says otherwise."""
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    monkeypatch.setattr(hub_auth, "colab_secret_token", lambda *a, **k: None)
    monkeypatch.setattr(hub_auth, "ambient_token", lambda: None)
    return monkeypatch


def _accepts(*good: str):
    return lambda token: token in good


def test_gated_model_without_a_token_names_the_licence(monkeypatch):
    monkeypatch.setattr(hub_auth, "token_is_accepted", _accepts())
    monkeypatch.setattr(hub_auth, "fetch_model_info", lambda *a, **k: FakeInfo())

    with pytest.raises(HubAccessError) as caught:
        check_model_access("google/gemma-2-2b-it")

    message = str(caught.value)
    assert "gated" in message
    assert "huggingface.co/google/gemma-2-2b-it" in message
    assert "HF_TOKEN" in message


def test_metadata_is_not_an_access_check(monkeypatch):
    """The regression: public metadata plus a refused download must fail here.

    ``model_info`` succeeds anonymously for a gated repository, so the preflight
    has to exercise the download. Before this, the notebook passed the preflight
    and then failed every example with a 401.
    """
    monkeypatch.setattr(hub_auth, "token_is_accepted", _accepts())
    monkeypatch.setattr(hub_auth, "fetch_model_info", lambda *a, **k: FakeInfo())

    def refuse(model_id, *, revision=None, token=None):
        raise OSError(
            "You are trying to access a gated repo. Make sure you have access to it at "
            f"https://huggingface.co/{model_id}. 401 Client Error. (Request ID: Root=1-abc)"
        )

    monkeypatch.setattr(hub_auth, "download_probe", refuse)

    with pytest.raises(HubAccessError) as caught:
        check_model_access("google/gemma-2-2b-it", token=SECRET)



def test_a_stale_ambient_token_falls_back_to_the_secret(monkeypatch):
    """A rejected token must be replaced, not trusted, and never hide the secret."""
    monkeypatch.setattr(hub_auth, "colab_secret_token", lambda *a, **k: SECRET)
    monkeypatch.setattr(hub_auth, "ambient_token", lambda: STALE)
    monkeypatch.setattr(hub_auth, "token_is_accepted", _accepts(SECRET))
    monkeypatch.setattr(hub_auth, "fetch_model_info", lambda *a, **k: FakeInfo())
    monkeypatch.setattr(hub_auth, "download_probe", lambda *a, **k: "/tmp/config.json")

    report = check_model_access("google/gemma-2-2b-it")

    assert report.token_source == "colab secret"
    assert os.environ["HF_TOKEN"] == SECRET  # the subprocess inherits what we validated
    assert STALE not in report.summary()


def test_a_rejected_token_is_reported_by_name(monkeypatch):
    monkeypatch.setattr(hub_auth, "ambient_token", lambda: STALE)
    monkeypatch.setattr(hub_auth, "token_is_accepted", _accepts())
    monkeypatch.setattr(hub_auth, "fetch_model_info", lambda *a, **k: FakeInfo())

    with pytest.raises(HubAccessError) as caught:
        check_model_access("meta-llama/Llama-3.2-3B-Instruct")

    assert "'environment'" in str(caught.value)
    assert "revoked" in str(caught.value)


def test_resolve_skips_empty_candidates():
    resolved, rejected = resolve_hub_token([("colab secret", None), ("environment", None)])
    assert resolved is None
    assert rejected == ()


def test_public_model_needs_no_token(monkeypatch):
    monkeypatch.setattr(hub_auth, "token_is_accepted", _accepts())
    monkeypatch.setattr(hub_auth, "fetch_model_info", lambda *a, **k: FakeInfo(gated=None))
    monkeypatch.setattr(hub_auth, "download_probe", lambda *a, **k: "/tmp/config.json")

    report = check_model_access("Qwen/Qwen2.5-3B-Instruct")

    assert report.is_gated is False
    assert "no token needed" in report.summary()
    assert "HF_TOKEN" not in os.environ


def test_the_probe_downloads_the_smallest_real_file(monkeypatch):
    seen: dict[str, object] = {}

    def record(model_id, *, revision=None, token=None):
        seen.update(model_id=model_id, revision=revision, token=token)
        return "/tmp/config.json"

    monkeypatch.setattr(hub_auth, "token_is_accepted", _accepts(SECRET))
    monkeypatch.setattr(hub_auth, "fetch_model_info", lambda *a, **k: FakeInfo())
    monkeypatch.setattr(hub_auth, "download_probe", record)

    report = check_model_access("google/gemma-2-2b-it", revision="main", token=SECRET)

    assert seen == {"model_id": "google/gemma-2-2b-it", "revision": "main", "token": SECRET}
    assert report.revision == FakeInfo.sha


def test_a_token_never_appears_in_an_error(monkeypatch):
    monkeypatch.setattr(hub_auth, "token_is_accepted", _accepts(SECRET))
    monkeypatch.setattr(hub_auth, "fetch_model_info", lambda *a, **k: FakeInfo())

    def leak(model_id, *, revision=None, token=None):
        raise OSError(f"401 for token {token}")

    monkeypatch.setattr(hub_auth, "download_probe", leak)

    with pytest.raises(HubAccessError) as caught:
        check_model_access("google/gemma-2-2b-it", token=SECRET)

    assert SECRET not in str(caught.value)
    assert "[REDACTED:credential]" in str(caught.value)


def test_the_underlying_error_is_bounded_and_single_line(monkeypatch):
    monkeypatch.setattr(hub_auth, "token_is_accepted", _accepts(SECRET))
    monkeypatch.setattr(hub_auth, "fetch_model_info", lambda *a, **k: FakeInfo())

    def noisy(model_id, *, revision=None, token=None):
        raise OSError("401\n" + "detail " * 500)

    monkeypatch.setattr(hub_auth, "download_probe", noisy)

    with pytest.raises(HubAccessError) as caught:
        check_model_access("google/gemma-2-2b-it", token=SECRET)

    underlying = caught.value.underlying or ""
    assert "\n" not in underlying
    assert len(underlying) <= hub_auth.MAX_UNDERLYING_CHARS

    assert "401" in str(caught.value)
    assert "metadata is public" in str(caught.value)
