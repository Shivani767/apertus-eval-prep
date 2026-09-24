"""Static Markdown and HTML reporting."""
from .markdown import render_run_markdown
from .html import render_run_html
from .safety import render_safety_html, render_safety_markdown
from .platform import load_report_payload, write_failure_fingerprint, write_run_reports

__all__ = [
    "render_run_markdown", "render_run_html", "render_safety_markdown", "render_safety_html",
    "load_report_payload", "write_failure_fingerprint", "write_run_reports",
]
