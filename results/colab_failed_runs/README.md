# Failed and superseded runs

Runs that did not produce usable measurements are kept here instead of in
[results/colab_real_model](../colab_real_model), so they cannot be mistaken for evidence
or silently dropped. Nothing here is cited: these are recorded attempts, not results.

## `gemma-2-2b-it/` - attempted 2026-09-26, 0 of 257 examples scored

Third and last attempt, from code commit `0cafa9e`, so the artifacts name the cause:

- **Status:** infrastructure failure, not a model-quality result. Every real run has
  `n_scored = 0`; the only scored run is the mock smoke, and the six-cell variance matrix has
  38 failures per cell. Nothing about Gemma's answers was measured.
- **Recorded cause:** every example carries
  `adapter_model_load_error: local model/tokenizer could not be loaded (OSError: You are
  trying to access a gated repo ... 401 Client Error. (Request ID: Root=1-6ab8073a-...))`.
  The Hub refused every weight download: no credential this session could use.
- **Why the preflight passed anyway**, which is the part worth keeping:
  1. `model_info` is not an access check. A gated repository publishes its metadata to
     anonymous callers, so the notebook printed `model access OK` and only the *file*
     downloads failed.
  2. An ambient token was accepted without validation, so a revoked or expired token was
     reported as "a token is already available" and the Colab secret was never read.
- **Fixed on master** by `apertus_eval_prep.hub_auth`: every candidate token is validated
  against `whoami` (an authenticated endpoint), the Colab secret is preferred over a cached
  token so a rotated value takes effect, the validated token is published to the
  subprocess that downloads the weights, and the preflight now fetches `config.json`, i.e.
  the download that was failing. Covered by `tests/test_hub_auth.py`; all ten notebooks
  delegate to it, enforced by `tests/test_notebook_hub_auth.py`.
- **Re-run:** open `notebooks/real_model_gemma-2-2b-it.ipynb` from GitHub master, restart
  the runtime, and run all cells. Section 0 now stops the session with the licence
  instructions and the underlying Hub error instead of letting 257 examples fail; once it
  prints `model access OK: google/gemma-2-2b-it (gated (auto), token from colab secret,
  revision <sha>)`, the steps will load.
- **Notebook state:** this notebook was regenerated from the template, so its stored
  outputs from the failed attempt are gone. Nothing was lost: the artifacts of that attempt
  are the ones preserved in this directory. The two notebooks whose runs *succeeded*
  (`real_model_qwen2.5-1.5b-instruct`, `real_model_smollm2-1.7b-instruct`) were deliberately
  left untouched, so their session records still exist.

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
