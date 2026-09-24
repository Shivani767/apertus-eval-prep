"""
Create master_results.tex table consolidating all results.
"""
import os

BASE = '/Users/shivanibhandari/Downloads/ETH : EPFL Apertus /apertus-eval-prep/paper'
master_table_path = os.path.join(BASE, 'tables', 'master_results.tex')

master_table_content = r"""\begin{table}[tbp]
\centering\footnotesize
\caption{Master results table: all 31 completed configurations across 4 models and 5 factor families. Accuracy in \% with Wilson 95\% CIs. $\Delta$ is change from each model's control configuration in percentage points. Holm-adjusted $p$-values from McNemar test against control. Bold ($\ast$) indicates statistically significant change after Holm correction ($p < 0.05$). The three missing Phi-3.5-mini sampling cells are listed as ``planned, not run''.}
\label{tab:master}
\begin{tabular}{llcccccccccc}
\toprule
& & \multicolumn{2}{c}{Phi-3.5-mini} & \multicolumn{2}{c}{Qwen2.5-3B} & \multicolumn{2}{c}{SmolLM2-1.7B} & \multicolumn{2}{c}{Qwen2.5-7B} \\
\cmidrule(lr){3-4} \cmidrule(lr){5-6} \cmidrule(lr){7-8} \cmidrule(lr){9-10}
Factor & Level & Acc. & $\Delta$ & Acc. & $\Delta$ & Acc. & $\Delta$ & Acc. & $\Delta$ \\
\midrule
\multicolumn{10}{c}{\textit{Control configuration (baseline)}} \\
 & Default & 67.0 & -- & 64.4 & -- & 39.8 & -- & -- & -- \\
\midrule
\multicolumn{10}{c}{\textit{Prompt variations}} \\
Prompt & Concise & 58.9 & -8.13$^{\ast}$ & 51.2 & -13.13$^{\ast}$ & 23.2 & -16.50$^{\ast}$ & -- & -- \\
Prompt & 5-shot & 56.4 & -10.63$^{\ast}$ & 68.6 & +4.25 & 34.2 & -5.50$^{\ast}$ & -- & -- \\
\midrule
\multicolumn{10}{c}{\textit{Quantization (weight-only, bitsandbytes)}} \\
Quant & INT8 & 67.2 & +0.25 & 64.8 & +0.37 & 41.8 & +2.00 & -- & -- \\
Quant & INT4 & 69.9 & +2.87 & 65.6 & +1.25 & 38.6 & -1.13 & 67.9 & -- \\
\midrule
\multicolumn{10}{c}{\textit{Infrastructure backend}} \\
Backend & vLLM & 67.1 & +0.12 & 66.8 & +2.37 & 42.0 & +2.25 & -- & -- \\
\midrule
\multicolumn{10}{c}{\textit{Greedy decoding seed}} \\
Seed & 1 & 67.0 & +0.00 & 64.4 & +0.00 & 39.8 & +0.00 & -- & -- \\
Seed & 2 & 67.0 & +0.00 & 64.4 & +0.00 & 39.8 & +0.00 & -- & -- \\
\midrule
\multicolumn{10}{c}{\textit{Sampling (temperature 0.7, top-$p$ 0.95)}} \\
Sample & T0.7, s0 & -- & (planned) & 64.2 & -0.13 & 36.2 & -3.50 & -- & -- \\
Sample & T0.7, s1 & -- & (planned) & 65.0 & +0.62 & 37.6 & -2.13 & -- & -- \\
Sample & T0.7, s2 & -- & (planned) & 63.0 & -1.38 & 39.0 & -0.75 & -- & -- \\
\bottomrule
\multicolumn{10}{l}{\small $^{\ast}$ Statistically significant after Holm correction over 27-contrast family ($p < 0.05$).}\\
\multicolumn{10}{l}{\small Qwen2.5-7B INT4 cell has no control for comparison; $\Delta$ not applicable.}\\
\multicolumn{10}{l}{\small Phi-3.5-mini sampling cells are planned but not yet executed (compute limitation).}\\
\end{tabular}
\end{table}

\smallskip
\noindent\textbf{Reading guide:} This table consolidates all results from
\cref{tab:control,tab:sensitivity,tab:sampling,tab:ranking}. Each row is one
configuration cell; the $\Delta$ column shows the change from that model's
control configuration. The three missing Phi-3.5-mini sampling cells are
listed as ``planned'' to document the gap explicitly.
"""

with open(master_table_path, 'w') as f:
    f.write(master_table_content)
print(f"Created {master_table_path}")