"""Rebuild every report in a curated Colab results directory from stored artifacts.

Rendering only: no GPU, no re-inference, and no metric is recomputed. Run this after a
reporting change so the committed reports match the code that produced them, and after
curating a new model's export so all of its reports share one style.

Usage:
    python3 scripts/regenerate_colab_reports.py results/colab_real_model/SmolLM2-1.7B-Instruct
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:  # run from a checkout without an editable install
    sys.path.insert(0, str(ROOT / "src"))

from apertus_eval_prep.experiments.reporting import render_experiment_html, render_experiment_markdown
from apertus_eval_prep.reporting.platform import write_run_reports
from apertus_eval_prep.study.reporting import write_study_outputs
from apertus_eval_prep.utils.serialization import read_json, write_text


def regenerate_run_reports(root: Path) -> int:
    """Rebuild report.md/report.html for every run directory."""
    count = 0
    for run_dir in sorted({path.parent for path in root.rglob("manifest.json")}):
        write_run_reports(run_dir, report_format="both")
        count += 1
    return count


def regenerate_experiment_reports(root: Path) -> int:
    """Rebuild <experiment>.experiment.{md,html} from the stored matrix result."""
    count = 0
    for path in sorted(root.rglob("*.experiment.json")):
        payload = read_json(path)
        write_text(path.with_suffix(".md"), render_experiment_markdown(payload))
        write_text(path.with_suffix(".html"), render_experiment_html(payload))
        count += 1
    return count


def regenerate_study_reports(root: Path) -> int:
    """Rebuild the study bundle (report, tables, manifest) from study_summary.json."""
    summary_path = root / "study" / "study_summary.json"
    if not summary_path.exists():
        return 0
    write_study_outputs(read_json(summary_path), root / "study")
    return 1


def regenerate_safety_reports(root: Path) -> int:
    """Rebuild safety_report.{md,html} for safety runs that already have one."""
    from apertus_eval_prep.reporting.platform import load_report_payload
    from apertus_eval_prep.reporting.safety import render_safety_html, render_safety_markdown

    count = 0
    for run_dir in sorted({path.parent for path in root.rglob("manifest.json")}):
        if not (run_dir / "safety_report.md").exists():
            continue
        payload = load_report_payload(run_dir)
        write_text(run_dir / "safety_report.md", render_safety_markdown(payload))
        write_text(run_dir / "safety_report.html", render_safety_html(payload))
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, help="Curated result directory, e.g. results/colab_real_model/<model>")
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"not a directory: {args.root}")
    runs = regenerate_run_reports(args.root)
    safety = regenerate_safety_reports(args.root)
    experiments = regenerate_experiment_reports(args.root)
    studies = regenerate_study_reports(args.root)
    print(
        f"regenerated under {args.root}: {runs} run reports, {safety} safety reports, "
        f"{experiments} experiment reports, {studies} study bundle(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
