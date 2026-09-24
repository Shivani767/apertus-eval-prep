>>> 🔬 reliability.py
Purpose: scoring-system sensitivity and reliability diagnosis.
Status: implemented and wired (134 lines, first file touched in the repo and in paper matrix).
What exists: per-experiment sensitivity profile (score SD, %change, fragility) when a scoring
system is swapped; the config-space ERS derivations on a model×config score matrix; ERS
decomposition (decision_prior, decision_consistency, config_fullness, scoring_consistency
with intended-source and cross-system consistency variants); perturbation diagnostics
(perturb_pairwin_counts / perturb_decision_reversals); _bootstrap_pairwin / bootstrap CI of
p_hat; ERS components run on both synthetic JUDGMENT matrices and the real GOLD registry rows;
ERS metadata-as-config-version diagnostics; and function-level ERS in-engine diagnostics.
What is missing: none critical for Stages 0-2; ERS is estimated from observed configs, so
held-out validation (Phase 5) is implemented separately in heldout.py and the analyzer.
Key nuance: the module already frames ERS correctly as a prediction target (held-out stability
under config shift), not ground truth — research_formulation.md reinforces this.
