#!/usr/bin/env python3
"""Fix discussion.tex - replace old limitations with structured threats to validity."""
import os

path = '/Users/shivanibhandari/Downloads/ETH : EPFL Apertus /apertus-eval-prep/paper/discussion.tex'

with open(path, 'r') as f:
    lines = f.readlines()

# Find the start and end of the old Limitations section
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if '\\section{Limitations}' in line:
        start_idx = i
    if start_idx is not None and '\\section{Ethical Considerations}' in line:
        end_idx = i
        break

if start_idx is None:
    print('ERROR: Could not find Limitations section')
elif end_idx is None:
    print('ERROR: Could not find Ethical Considerations section')
else:
    print(f'Found Limitations section: lines {start_idx+1} to {end_idx}')
    
    # Build replacement lines
    new_lines = [
        '\\section{Threats to Validity and Limitations}\n',
        '\\label{sec:limitations}\n',
        '\n',
        'We organize threats to validity following conventional categories, adapted\n',
        'for an artifact-based observational study.\n',
        '\n',
        '\\subsection{Construct validity}\n',
        '\\textit{What we measure may not correspond to what we claim to measure.}\n',
        '\n',
        '\\begin{itemize}\n',
        '  \\item \\textbf{Scoring protocol.} Generative exact-match with letter/number\n',
        'extraction differs from the log-likelihood multiple-choice protocol used by\n',
        'standard leaderboards.\n',
        '  \\item \\textbf{Extractor validation.} The permissive parser has not been\n',
        'independently adjudicated.\n',
        '  \\item \\textbf{Task coverage.} Four tasks do not represent the full\n',
        'space of LLM capabilities.\n',
        '  \\item \\textbf{Contamination.} Benchmark contamination is unmeasured here.\n',
        '\\end{itemize}\n',
        '\n',
        '\\subsection{Internal validity}\n',
        '\\textit{Explanations other than the configuration change may account for observed differences.}\n',
        '\n',
        '\\begin{itemize}\n',
        '  \\item \\textbf{Software drift.} Runs span 14 distinct git commits with\n',
        'varying package versions.\n',
        '  \\item \\textbf{Model revisions.} Model and tokenizer hub revisions were\n',
        'not pinned in run manifests.\n',
        '  \\item \\textbf{Precision.} Recorded as \\texttt{dtype=auto}.\n',
        '  \\item \\textbf{Post-hoc selection.} The Phi/Qwen comparison was\n',
        'selected after observing top scores.\n',
        '\\end{itemize}\n',
        '\n',
        '\\subsection{External validity}\n',
        '\\textit{Results may not generalize beyond the measured setting.}\n',
        '\n',
        '\\begin{itemize}\n',
        '  \\item \\textbf{Model scale.} Three models (1.7B--3.8B) plus one 7B cell.\n',
        '  \\item \\textbf{Benchmark slices.} 200-item slices are small.\n',
        '  \\item \\textbf{Hardware.} All runs on NVIDIA Tesla T4.\n',
        '  \\item \\textbf{Sampling coverage.} Missing Phi-3.5-mini sampling cells.\n',
        '  \\item \\textbf{Configuration space.} Other dimensions not explored.\n',
        '\\end{itemize}\n',
        '\n',
        '\\subsection{Statistical conclusion validity}\n',
        '\\textit{Statistical inferences may be weakened by assumption violations.}\n',
        '\n',
        '\\begin{itemize}\n',
        '  \\item \\textbf{Item dependence.} MGSM translations and GSM8K questions\n',
        'are not independent.\n',
        '  \\item \\textbf{Multiple testing.} Holm--Bonferroni is conservative.\n',
        '  \\item \\textbf{Interval interpretation.} Wilson intervals assume\n',
        'binomial sampling.\n',
        '  \\item \\textbf{Paired test assumptions.} McNemar assumes independent\n',
        'discordant pairs.\n',
        '  \\item \\textbf{Bootstrap scope.} Resamples configurations, not items.\n',
        '\\end{itemize}\n',
        '\n',
        '\\subsection{Measurement and recording limitations}\n',
        '\\textit{Data quality and completeness constraints.}\n',
        '\n',
        '\\begin{itemize}\n',
        '  \\item \\textbf{Missing cells.} Three Phi-3.5-mini sampling cells missing.\n',
        '  \\item \\textbf{Latency placeholders.} vLLM cells store 0.0 timing.\n',
        '  \\item \\textbf{Reproducibility scope.} Analysis reproduction feasible.\n',
        '  \\item \\textbf{OFAT, not factorial.} Full factorial (Prompt $\\times$ Runtime $\\times$\n',
        'Seed) planned and committed to \\texttt{t4\_factorial.yaml}.\n',
        '\\end{itemize}\n',
        '\n',
    ]
    
    final_lines = lines[:start_idx] + new_lines + lines[end_idx:]
    
    with open(path, 'w') as f:
        f.writelines(final_lines)
    
    print('Discussion updated successfully')