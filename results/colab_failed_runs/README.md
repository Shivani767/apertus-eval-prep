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

- **Status:** infrastructure failure. Every real run has `n_scored = 0` and 38 failures per
  variance cell; the responses are `[ADAPTER_FAILURE]` with
  `adapter_model_load_error: local model/tokenizer could not be loaded`. Nothing about the
  model's answers was measured.
- **Unlike the Gemma attempt, this run used a current notebook**: code commit `be36970`,
  which already contains the `## 0. Authenticate for gated models` cell, and the run
  recorded the pinned revision `0cb88a4f764b7a12671c53f0838cd831a0843b95`. So the failure is
  not a stale checkout.
- **The underlying cause is not in the artifacts**, because `be36970` predates the adapter
  fix that puts it there. Run the tokenizer/model load in a single cell to see the real
  error; the most likely candidates are a token whose repository scope excludes
  `meta-llama/Llama-3.2-3B-Instruct` (fine-grained tokens can be limited per repository),
  or the pinned revision not being reachable with the granted access.
- **Re-run:** after the load succeeds in that one cell, the platform steps will too, and the
  next export will be a measured run. This is the first run that would record a pinned
  revision, so its summary should carry no unpinned-revision warning.
