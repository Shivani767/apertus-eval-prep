# Failed and superseded runs

Runs that did not produce usable measurements are kept here instead of in
[results/colab_real_model](../colab_real_model), so they cannot be mistaken for evidence
or silently dropped. Nothing here is cited: these are recorded attempts, not results.

## `gemma-2-2b-it/` - attempted 2026-09-26, 0 of 257 examples scored

- **Status:** infrastructure failure, not a model-quality result. Every real run has
  `n_scored = 0` and the only scored run is the mock smoke; the six-cell variance matrix
  has 38 failures per cell.
- **Recorded cause:** every example carries
  `adapter_model_load_error: local model/tokenizer could not be loaded`, category
  `timeout_or_infrastructure_failure`. The weights were never loaded, so nothing about the
  model's answers was measured.
- **Why:** the session ran a notebook checkout from code commit `ee11d9b`, which predates
  the `## 0. Authenticate for gated models` cell (`b52fc09`). Without that cell the Colab
  `HF_TOKEN` secret is never copied into the environment, so the `platform-*` subprocess
  that downloads the gated weights had no token and the Hub returned 401.
- **Not a Gemma problem:** the same token/secret path works for ungated models, and the
  preflight in the current notebook reports the access problem before any run starts.
- **Re-run:** open `notebooks/real_model_gemma-2-2b-it.ipynb` from GitHub master, confirm
  the section 0 cell exists, run it so it prints `model access OK: google/gemma-2-2b-it`,
  then curate the new export as usual. A fresh summary will show whether the runs scored.

Load errors now name their underlying cause, so the next attempt of this kind records the
Hub 401 in the artifacts instead of a generic message.

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
