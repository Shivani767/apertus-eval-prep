#!/usr/bin/env python3
"""Rewrite results.tex with proper formatting."""
import os

path = '/Users/shivanibhandari/Downloads/ETH : EPFL Apertus /apertus-eval-prep/paper/results.tex'

new_content = r"""\section{Results: Score Sensitivity}
\label{sec:results}

\subsection{Control configuration}
\label{sec:control}

\cref{tab:control} reports the control accuracies. Phi-3.5-mini scores
67.0\% and Qwen2.5-3B 64.4\%; their Wilson intervals overlap ([63.7, 70.2] vs.
[61.0, 67.6]), so under the interval-aware convention the control
configuration does not statistically separate the top two models.
SmolLM2-1.7B (39.8\%) is separated from both. We emphasize this because the
magnitude of every subsequent configuration effect should be read against a
top-two gap that is itself small and interval-overlapping.

\cref{tab:master} provides a consolidated view of all configuration results.
\cref{fig:matrix} diagrams the experimental matrix.

\subsection{Prompt changes are the dominant factor}
\label{sec:prompt}

\cref{fig:prompt} and \cref{tab:sensitivity} give the central sensitivity
result. The \emph{concise} prompt is harmful everywhere, and its harm is
concentrated in generative math: SmolLM2-1.7B drops 16.50\,\pp{} (39.75\%$\to$
23.25\%), Qwen2.5-3B drops 13.13\,\pp{} (64.38\%$\to$51.25\%), and Phi-3.5-mini
drops 8.13\,\pp{} (67.00\%$\to$58.88\%). All three McNemar contrasts remain
significant after Holm correction ($p<0.001$ adjusted), with small-to-medium
effect sizes ($h=-0.36$, $-0.27$, $-0.17$).

Task-level breakdowns locate the damage: Qwen2.5-3B GSM8K falls from 85/200
to 30/200 and MGSM from 84/200 to 28/200 under \emph{concise}, while ARC is
nearly unchanged (192/200$\to$195/200)---the minimal instruction removes the
step-by-step scaffold that the math tasks depend on.

The \emph{5-shot} prompt has model-dependent, sign-changing effects. It
\emph{helps} Qwen2.5-3B ($+4.25$\,pp{} to 68.63\%; raw McNemar $p=0.0035$,
not significant after Holm at $0.078$), \emph{hurts} SmolLM2-1.7B ($-5.50$\,pp{}
to 34.25\%; Holm-adjusted $p=0.037$), and \emph{hurts} Phi-3.5-mini by
10.63\,\pp{} (to 56.37\%; Holm-adjusted $p<0.001$). The per-task pattern
explains the Phi drop: five-shot exemplars lift its GSM8K (95/200$\to$140/200)
and MGSM (84/200$\to$105/200) but collapse its ARC accuracy from 197/200 to
68/200, apparently disrupting letter-answer extraction. The same factor
therefore moves different models in different directions---an interaction-
shaped pattern that the OFAT design surfaces qualitatively but cannot
estimate formally (\cref{sec:factorial-plan}).

\input{tables/main_results.tex}

\begin{figure}[t]
\centering
\includegraphics[width=0.9\linewidth]{experimental_matrix.pdf}
\caption{Experimental matrix: 34-cell planned design with 31 completed cells
(shaded) and 3 missing cells (outlined, Phi-3.5-mini sampling). Each column
is a factor family; each row is a model. The OFAT design varies one factor at
a time from the control. The planned factorial experiment (Prompt $\times$
Runtime $\times$ Seed) would fill the crossed cells to enable interaction
analysis. See \cref{tab:master} for the full results table.}
\label{fig:matrix}
\end{figure}
"""

with open(path, 'w') as f:
    f.write(new_content)

print(f"Rewrote {path}")