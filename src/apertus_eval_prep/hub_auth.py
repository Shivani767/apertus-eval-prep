"""Hugging Face credential resolution and a preflight that can actually fail a gated model.

Why this module exists
----------------------
A real Colab run of ``google/gemma-2-2b-it`` scored 0 of 257 examples: the Hub
answered ``401 Unauthorized`` for every weight download, while the notebook
preflight had already printed ``model access OK``. Two independent mistakes
combined to produce that silent failure:

* ``model_info`` is not an access check. A gated repository publishes its
  metadata to anonymous callers, so ``model_info`` succeeds with no credential
  at all and only the *file* download fails. A preflight that stops there
  cannot detect the problem it exists to detect.
* An ambient token was accepted without validation. ``authenticate_hugging_face``
  returned early whenever ``HF_TOKEN`` or the on-disk token existed, so a revoked
  or expired token was reported as "a token is already available", the Colab
  secret was never read, and the subprocess that downloads the weights
  inherited nothing that works.

So credential resolution here has three properties:

* **Order is explicit**: an argument, then the Colab secret, then the ambient
  environment or on-disk token. A newly rotated secret takes effect instead of
  being masked by a stale cached token.
* **Every candidate is validated** against ``whoami``, an endpoint that requires
  authentication. Rejected candidates are reported, never trusted.
* **The download path is proven** by fetching the smallest real file, which is
  the exact operation that returns 401 for a gated model.

Tokens are never logged, never returned in messages, and never written to disk;
the validated token is published into ``os.environ`` only so that the platform
subprocess inherits the credential the preflight just proved.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from apertus_eval_prep.utils.pii import redact_text_for_artifact

#: Smallest real file in a model repository: enough to exercise the download
#: path without pulling weights.
PROBE_FILENAME = "config.json"

#: The part of a Hub error worth keeping in a message. Bounded because the text
#: is rendered in a notebook and in an exception chain.
MAX_UNDERLYING_CHARS = 300


class HubAccessError(RuntimeError):
    """Raised when the Hub will not serve a model to this session.

    Carries the instructions that unblock a gated repository plus the underlying
    Hub error, so a failure is diagnosable from the traceback alone instead of
    from a later run of 257 identical adapter failures.
    """

    def __init__(self, message: str, *, model_id: str, underlying: str | None = None) -> None:
        super().__init__(message)
        self.model_id = model_id
        self.underlying = underlying


def gated_hint(model_id: str) -> str:
    """The instructions for a gated repository, in one reusable string."""
    return (
        f"This model is gated. (1) Accept its licence at https://huggingface.co/{model_id} while "
        "signed in as the account that runs this notebook. (2) Create a read-only token at "
        "https://huggingface.co/settings/tokens. (3) In Colab add it as the secret HF_TOKEN (key "
        "icon in the left panel). Never put a token in a notebook, a config, or a commit. Public "
        "models need none of this."
    )


def _underlying(exc: BaseException) -> str:
    """A redacted, single-line, length-bounded rendering of a Hub exception."""
    text = " ".join(str(exc).split())
    return redact_text_for_artifact(text)[:MAX_UNDERLYING_CHARS]




def colab_secret_token(secret_name: str = "HF_TOKEN") -> str | None:
    """Return the token stored in a Colab secret, or ``None`` outside Colab."""
    try:
        from google.colab import userdata
    except Exception:
        return None
    try:
        return userdata.get(secret_name) or None
    except Exception:
        # Colab raises when the secret is absent or unreadable; that is "no token".
        return None


def ambient_token() -> str | None:
    """Return a token already visible to this process, *without* validating it."""
    try:
        from huggingface_hub import get_token
    except Exception:
        get_token = None  # type: ignore[assignment]
    if get_token is not None:
        try:
            cached = get_token()
        except Exception:
            cached = None
        if cached:
            return str(cached)
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value
    return None


def token_is_accepted(token: str) -> bool:
    """True when the Hub recognises this token.

    ``whoami`` requires authentication, so it fails for a missing, malformed,
    expired or revoked token. That is precisely the question a preflight has to
    answer, and ``model_info`` cannot answer it.
    """
    try:
        from huggingface_hub import HfApi
    except Exception:
        return False
    try:
        HfApi().whoami(token=token)
    except Exception:
        return False
    return True


def resolve_hub_token(
    candidates: Sequence[tuple[str, str | None]],
) -> tuple[str | None, tuple[str, ...]]:
    """Return the first accepted candidate, and the names that were rejected.

    Candidates are tried in the given order and each one is validated, so a stale
    cached token is reported as rejected instead of being trusted, and the next
    source gets its turn. Rejected names are returned for the error message: they
    say *which* source was wrong, which is what makes a 401 diagnosable.
    """
    rejected: list[str] = []
    for name, token in candidates:
        if not token:
            continue
        if token_is_accepted(token):
            return token, tuple(rejected)
        rejected.append(name)
    return None, tuple(rejected)


def fetch_model_info(model_id: str, *, revision: str | None = None, token: str | None = None) -> Any:
    """Repository metadata. Public for gated repositories, so it is not a check."""
    from huggingface_hub import HfApi

    return HfApi().model_info(model_id, revision=revision, token=token)


def download_probe(model_id: str, *, revision: str | None = None, token: str | None = None) -> str:
    """Fetch the smallest real file: the operation a gated run depends on."""
    from huggingface_hub import hf_hub_download

    return hf_hub_download(model_id, PROBE_FILENAME, revision=revision, token=token)


@dataclass(frozen=True)
class AccessReport:
    """The outcome of a successful preflight."""

    model_id: str
    revision: str | None
    gated: str | None
    token_source: str | None

    @property
    def is_gated(self) -> bool:
        return bool(self.gated)

    def summary(self) -> str:
        """One line for a notebook, with the pin, and never a token."""
        if self.is_gated:
            state = f"gated ({self.gated}), token from {self.token_source}"
        else:
            state = "public, no token needed"
        sha = f", revision {self.revision}" if self.revision else ""
        return f"model access OK: {self.model_id} ({state}{sha})"


def _rejection_note(rejected: Sequence[str]) -> str:
    if not rejected:
        return ""
    listed = ", ".join(repr(name) for name in rejected)
    return (
        f"\n\nA token was found in {listed} but the Hub rejected it. A revoked, expired or "
        "mistyped token looks exactly like no token: re-create it, and replace the Colab secret "
        "so the new value is picked up."
    )


def check_model_access(
    model_id: str,
    *,
    revision: str | None = None,
    token: str | None = None,
    probe: bool = True,
) -> AccessReport:
    """Prove this session can load ``model_id``, or explain why it cannot.

    Raises :class:`HubAccessError` with the licence instructions and the
    underlying Hub error. Returns an :class:`AccessReport` carrying the resolved
    revision, so a notebook can pin the exact commit it measured.
    """
    if token:
        candidates: list[tuple[str, str | None]] = [("argument", token)]
    else:
        # Secret before environment: a rotated secret must not be masked by a
        # token that an earlier login() cached on disk.
        candidates = [("colab secret", colab_secret_token()), ("environment", ambient_token())]

    resolved, rejected = resolve_hub_token(candidates)
    source = next((name for name, value in candidates if resolved and value == resolved), None)
    if resolved:
        # The platform runs in a subprocess that downloads the weights; give it
        # exactly the credential this preflight just validated.
        os.environ["HF_TOKEN"] = resolved

    try:
        info = fetch_model_info(model_id, revision=revision, token=resolved)
    except Exception as exc:
        underlying = _underlying(exc)
        raise HubAccessError(
            f"The Hub did not return metadata for {model_id}."
            + _rejection_note(rejected)
            + f"\n\nUnderlying error: {underlying}",
            model_id=model_id,
            underlying=underlying,
        ) from exc

    gated = getattr(info, "gated", None)
    sha = getattr(info, "sha", None)

    if gated and not resolved:
        raise HubAccessError(
            f"{model_id} is a gated repository ({gated}) and this session has no token the Hub "
            f"accepts.{_rejection_note(rejected)}\n\n{gated_hint(model_id)}",
            model_id=model_id,
        )

    if probe:
        try:
            download_probe(model_id, revision=revision, token=resolved)
        except Exception as exc:
            underlying = _underlying(exc)
            raise HubAccessError(
                f"The Hub served metadata for {model_id} but refused to download "
                f"{PROBE_FILENAME}. Repository metadata is public even for gated models, so a "
                "metadata check alone would have passed while every weight download failed."
                f"{_rejection_note(rejected)}\n\n{gated_hint(model_id)}"
                f"\n\nUnderlying error: {underlying}",
                model_id=model_id,
                underlying=underlying,
            ) from exc

    return AccessReport(model_id=model_id, revision=sha, gated=gated, token_source=source)

    return None, tuple(rejected)
