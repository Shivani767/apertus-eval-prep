# Official frozen slices

Eval never downloads these at scoring time. Generate (or refresh) with:

```bash
pip install -e ".[snapshot]"
python scripts/snapshot_benchmarks.py --force
```

Then commit the JSONL. Provenance, licenses, Hub revisions, and the shuffle rule are in [SOURCES.md](SOURCES.md) after the snapshot runs.

Protocol: generative exact-match (letter or last number). Not lm-eval loglikelihood.
