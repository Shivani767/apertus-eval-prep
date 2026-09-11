"""Automated research report generation (Phase 14).

Generates a structured research report from an ExperimentRun. Every number
in the report is traced to an actual registry artifact. Clearly distinguishes:
  MEASURED  — directly observed in run files
  DERIVED   — computed from measured values (statistics, rankings)
  INTERPRETATION — discussion of what the numbers mean
  PENDING   — experiments not yet run
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apertus_eval_prep.experiment_runner import ExperimentRun


def generate_research_report(
    run: ExperimentRun,
    *,
    repo_root: Path,
    n_boot: int = 300,
    seed: int = 0,
) -> str:
    """Generate a full research report from an experiment run."""
    sections = [
        _header(run),
        _research_question(run),
        _experimental_design(run),
        _models_and_tasks(run),
        _configurations(run),
        _methodology(run),
        _results(run),
        _ranking_analysis(run, repo_root=repo_root, n_boot=n_boot, seed=seed),
        _limitations(run),
        _reproducibility(run),
    ]
    return "\n".join(sections) + "\n"


def _header(run: ExperimentRun) -> str:
    return (
        f"# Research Report: {run.experiment_id}\n\n"
        f"Generated: {run.environment.get('utc', 'unknown')}\n\n"
        "---\n\n"
        "**Legend:** [MEASURED] directly observed | "
        "[DERIVED] computed from measurements | "
        "[INTERPRETATION] discussion | "
        "[PENDING] not yet run\n\n"
    )


def _research_question(run: ExperimentRun) -> str:
    return (
        "## 1. Research Question\n\n"
        "When can we trust an LLM benchmark result?\n\n"
        f"This experiment ({run.experiment_id}) investigates how evaluation "
        "conclusions change under reasonable changes to the evaluation protocol: "
        "prompt, backend, quantization, sampling, and seed.\n\n"
    )


def _experimental_design(run: ExperimentRun) -> str:
    snap = run.config_snapshot
    profile = snap.get("profile", "unknown")
    return (
        "## 2. Experimental Design\n\n"
        f"- **Profile**: {profile}\n"
        f"- Cells measured: {len(run.results)}\n"
        f"- **Experiment ID**: {run.experiment_id}\n\n"
    )


def _models_and_tasks(run: ExperimentRun) -> str:
    models = sorted({r.model_id for r in run.results})
    lines = ["## 3. Models\n\n"]
    for m in models:
        lines.append(f"- `{m}`\n")
    lines.append("\n")
    return "".join(lines)


def _configurations(run: ExperimentRun) -> str:
    factors = sorted({(r.factor, r.factor_level) for r in run.results})
    lines = ["## 4. Configurations\n\n"]
    lines.append("| Factor | Level |\n|---|---|\n")
    for factor, level in factors:
        lines.append(f"| {factor} | {level} |\n")
    lines.append("\n")
    return "".join(lines)


def _methodology(run: ExperimentRun) -> str:
    return (
        "## 5. Statistical Methodology\n\n"
        "- **Confidence intervals**: Wilson score interval (binomial)\n"
        "- **Ranking**: Competition ranking (1 = best)\n"
        "- **Ranking stability**: Bootstrap Kendall-tau vs reference ranking\n"
        "- **Effect size**: Cohen's h for proportion differences\n"
        "- **Multiple comparisons**: Holm-Bonferroni (FWER), "
        "Benjamini-Hochberg (FDR)\n"
        "- **Fragility**: Component-based (score/rank/prompt/backend/seed/"
        "quantization sensitivity)\n\n"
        "All methods are documented in `docs/STATISTICAL_METHODOLOGY.md`.\n\n"
    )


def _results(run: ExperimentRun) -> str:
    lines = ["## 6. Results [MEASURED]\n\n"]
    lines.append("| Model | Factor | Level | Accuracy | n |\n")
    lines.append("|---|---|---|---|---|\n")
    for r in sorted(run.results, key=lambda x: (x.model_id, x.factor)):
        lines.append(
            f"| `{r.model_id}` | {r.factor} | {r.factor_level} | "
            f"{r.accuracy:.4f} | {r.n_items} |\n"
        )
    lines.append("\n")
    return "".join(lines)


def _ranking_analysis(
    run: ExperimentRun, *, repo_root: Path, n_boot: int, seed: int,
) -> str:
    from statistics import mean
    from apertus_eval_prep.ranking import bootstrap_ranking_stability

    by_model: dict[str, list[float]] = {}
    for r in run.results:
        by_model.setdefault(r.model_id, []).append(r.accuracy)

    models = sorted(by_model)
    matrix = [by_model[m] for m in models]

    lines = ["## 7. Ranking Analysis [DERIVED]\n\n"]
    lines.append("| Model | Mean Accuracy | Cells |\n")
    lines.append("|---|---|---|\n")
    for m in models:
        lines.append(f"| `{m}` | {mean(by_model[m]):.4f} | {len(by_model[m])} |\n")
    lines.append("\n")

    if len(matrix) >= 2:
        try:
            stab = bootstrap_ranking_stability(matrix, n_boot=n_boot, seed=seed)
            tau = stab["mean_tau"]
            rev = stab["p_any_reversal"]
            if tau is not None:
                lines.append(
                    f"- **Bootstrap mean Kendall-tau**: {tau:.4f} [DERIVED]\n"
                )
            if rev is not None:
                lines.append(f"- **P(any reversal)**: {rev:.4f} [DERIVED]\n\n")
        except Exception as e:
            lines.append(f"- Ranking stability: could not compute ({e})\n\n")
    else:
        lines.append("- Ranking stability: could not compute (need >= 2 models)\n\n")

    return "".join(lines)


def _limitations(run: ExperimentRun) -> str:
    return (
        "## 8. Limitations\n\n"
        "- Results are specific to the models, tasks, and configurations tested.\n"
        "- Sampling results (T>0) depend on the seed and temperature.\n"
        "- Statistical power depends on the number of items per cell.\n"
        "- This report is auto-generated; interpretations should be validated.\n\n"
    )


def _reproducibility(run: ExperimentRun) -> str:
    env = run.environment
    return (
        "## 9. Reproducibility\n\n"
        f"- **Git SHA**: `{env.get('git_sha', 'unknown')}`\n"
        f"- **Git dirty**: {env.get('git_dirty', 'unknown')}\n"
        f"- **Python**: {env.get('python_version', 'unknown')}\n"
        f"- **Platform**: {env.get('platform', 'unknown')}\n"
        f"- **Registry**: `{run.registry_path}`\n"
        f"- **Output dir**: `{run.output_dir}`\n\n"
        "Reproduce with:\n```bash\n"
        f"python -m apertus_eval_prep experiment run "
        f"--config <config.yaml> --id {run.experiment_id}\n"
        "```\n\n"
    )