#!/usr/bin/env python3
"""Update framework.tex - Add factorial experiment discussion."""
import os

BASE = '/Users/shivanibhandari/Downloads/ETH : EPFL Apertus /apertus-eval-prep/paper'
framework_path = os.path.join(BASE, 'framework.tex')

with open(framework_path, 'r') as f:
    content = f.read()

factorial_text = r"""
\subsection{Planned factorial experiment (Prompt $\times$ Runtime $\times$ Seed)}
\label{sec:factorial-plan}

The OFAT design isolates each factor's marginal effect but cannot estimate
interaction effects between configuration dimensions. We have designed a
full factorial experiment to address this limitation:
\begin{itemize}
  \item \textbf{Prompt}: default, concise, 5-shot (3 levels)
  \item \textbf{Runtime}: HF generate, vLLM (2 levels)
  \item \textbf{Seed}: 0, 1, 2 under greedy; 0, 1, 2 under temperature-0.7 sampling
\end{itemize}
A full $3 \times 2 \times 3$ factorial on the three main models would require
$18$ cells per model (54 total), with paired per-item artifacts enabling
analysis of interaction effects via logistic regression with configuration
interactions. The planned configuration is in \texttt{configs/experiments/t4\_factorial.yaml}. If compute becomes available, this factorial experiment would allow us to answer questions that OFAT cannot: Does the prompt effect depend on the backend? Does quantization interact with prompt complexity? Are sampling variances stable across prompt types?

"""

if '\\section{Related Work}' in content:
    content = content.replace(
        '\\section{Related Work}',
        factorial_text + '\n\\section{Related Work}'
    )
    with open(framework_path, 'w') as f:
        f.write(content)
    print("Updated framework.tex with factorial experiment discussion")
else:
    print("Could not find Related Work section")