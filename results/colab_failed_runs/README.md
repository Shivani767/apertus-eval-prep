# Failed and superseded runs

Runs that did not produce usable measurements are kept here instead of in
[results/colab_real_model](../colab_real_model), so they cannot be mistaken for evidence
or silently dropped. Nothing here is cited: these are recorded attempts, not results.

A model leaves this list once a later attempt of it measures successfully; the failed
attempts themselves stay in the git history.

## `gemma-2-2b-it/` - three failed attempts, now resolved

Resolved, so the directory is gone and the measured run lives in
[results/colab_real_model/Gemma-2-2B-Instruct](../colab_real_model/Gemma-2-2B-Instruct)
(257 of 257 scored, core mean 0.2105). Kept here because the failures are why the
authentication path is now tested:

1. The first attempt ran a checkout that predated the authentication cell, so the Colab
   secret never reached the process that downloads gated weights.
2. The second and third attempts authenticated, but the preflight only called
   `model_info`, which succeeds anonymously for a gated repository: its metadata is public,
   so the notebook printed `model access OK` while every weight download returned
   `401 Client Error`. The preflight also accepted any ambient `HF_TOKEN` without checking
   it, so a revoked token was reported as available and the Colab secret was never read.
3. `apertus_eval_prep.hub_auth` now validates every candidate against `whoami`, prefers the
   Colab secret over a cached token, publishes the validated token to the subprocess, and
   proves the download by fetching `config.json` before any GPU time is spent. Covered by
   `tests/test_hub_auth.py`, with `tests/test_notebook_hub_auth.py` holding the notebooks to
   the tested path.

The same two mistakes cost the Llama attempts below, which have not been re-run since the
fix landed.

## `llama-3.2-3b-instruct/` - attempted 2026-09-26, 0 of 257 examples scored

Second attempt, from code commit `5c6ec05`, with the pinned revision
`0cb88a4f764b7a12671c53f0838cd831a0843b95` recorded in every manifest.

- **Status:** infrastructure failure, not a model-quality result. Every real run has
  `n_scored = 0`; the only scored run is the mock smoke. Nothing about Llama's answers was
  measured.
- **Recorded cause:** every example carries
  `adapter_model_load_error: local model/tokenizer could not be loaded (OSError: You are
  trying to access a gated repo ... https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct.
  401 Client Error. (Request ID: Root=1-6ab80926-...))`. `401` is the Hub saying the
  credentials were absent or rejected, as distinct from `403`, which would mean valid
  credentials without the granted access. So this is a token problem, not a licence
  problem, and not a Llama problem.
- **Why the preflight still did not catch it:** this session ran `5c6ec05`, which predates
  the `hub_auth` fix, so it used the notebook's own unvalidated helper. The fix that now
  names the rejected source and probes the download is `9d2e275`; a notebook opened from
  master after that commit stops at section 0 with a named cause instead of running 257
  failing examples.
- **Re-run:** open `notebooks/real_model_llama-3.2-3b-instruct.ipynb` fresh from GitHub
  master, restart the runtime, and run all cells. Section 0 will either authenticate and
  print the revision to pin, or name the token source it rejected.
