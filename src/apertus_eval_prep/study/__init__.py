"""Phase 8 study configuration, analysis, and static reports."""
from .schema import StudySpec, load_study_config
from .compatibility import validate_study_compatibility
from .analysis import analyze_study
from .reporting import render_study_html, render_study_markdown, write_study_outputs

__all__ = [
    "StudySpec", "load_study_config", "validate_study_compatibility", "analyze_study",
    "render_study_markdown", "render_study_html", "write_study_outputs",
]
