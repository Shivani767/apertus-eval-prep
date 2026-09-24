"""Experiment matrix orchestration and run comparison."""
from .matrix import MatrixCell, MatrixResult, analyze_matrix_cells, run_experiment_matrix, run_matrix
from .compare import compare_run_directories, comparison_markdown
from .reporting import render_experiment_html, render_experiment_markdown

__all__ = ["MatrixCell", "MatrixResult", "analyze_matrix_cells", "run_experiment_matrix", "run_matrix", "compare_run_directories", "comparison_markdown", "render_experiment_html", "render_experiment_markdown"]
