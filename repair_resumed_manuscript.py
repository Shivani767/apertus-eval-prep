"""One-time manuscript repair; does not modify inference artifacts."""
from pathlib import Path
P = Path(__file__).resolve().parent / 'paper'
def replace(name, old, new):
    path = P / name
    text = path.read_text()
    assert text.count(old) == 1, (name, old[:80], text.count(old))
    path.write_text(text.replace(old, new))

path = P / 'references.bib'
text = path.read_text()
assert '@article{uthomas2024reproducibility,' in text
path.write_text(text.split('@article{uthomas2024reproducibility,')[0] + r'''
@article{white2024livebench,
  author = {White, Colin and Dooley, Samuel and Roberts, Manley and Pal, Arka and Feuer, Ben and Jain, Siddhartha and Shwartz-Ziv, Ravid and Jain, Neel and Saifullah, Khalid and Dey, Sreemanti and others},
  title = {{LiveBench}: A Challenging, Contamination-Limited {LLM} Benchmark},
  journal = {arXiv preprint arXiv:2406.19314},
  year = {2024},
  url = {https://arxiv.org/abs/2406.19314}
}
@article{lin2023awq,
  author = {Lin, Ji and Tang, Jiaming and Tang, Haotian and Yang, Shang and Chen, Wei-Ming and Wang, Wei-Chen and Xiao, Guangxuan and Dang, Xingyu and Gan, Chuang and Han, Song},
  title = {{AWQ}: Activation-aware Weight Quantization for {LLM} Compression and Acceleration},
  journal = {arXiv preprint arXiv:2306.00978},
  year = {2023},
  url = {https://arxiv.org/abs/2306.00978}
}
''')
path = P / 'framework.tex'
text = path.read_text()
text = text.split(r'\paragraph{Evaluation reproducibility.}')[0] + r'''
\paragraph{Reproducibility and benchmark reliability.}
\citet{biderman2024lessons} document sensitivity to evaluation setup and
recommend transparent reporting of evaluation conventions. Our paired
artifact audit operationalizes this recommendation, while distinguishing
stored-output reproducibility from historical inference replication.
LiveBench \citep{white2024livebench}, first released in 2024 and revised in
2025, uses frequently updated questions and objective ground-truth scoring
to limit contamination and judging bias. This addresses a different threat
from configuration sensitivity: our frozen public slices support paired
comparisons but do not establish freedom from contamination.

\paragraph{Quantization beyond the measured implementation.}
AWQ \citep{lin2023awq} uses activation information to protect salient weight
channels in low-bit weight-only quantization and evaluates language-model
and domain-specific benchmarks. Alongside k-bit scaling laws
\citep{dettmers2023case}, this shows why precision results must be tied to a
specific method and workload. We test bitsandbytes, not AWQ, and make no
claim that the small corrected effects here generalize to other quantizers.
'''
path.write_text(text)
replace('framework.tex', 'These systems pin\nprompts and metrics at the task level; the operator-level dimensions we\nablate (backend, quantization, decoding, seed) typically remain implicit\ndeployment choices rather than reported, ablated factors.', 'These systems provide configurable evaluation protocols. Our contribution\nis a bounded joint audit of operator choices and stored item outcomes,\nnot a claim that existing harnesses cannot configure these dimensions.')
replace('framework.tex', 'can be small while 21--24\\% of items change correctness state.', 'can be small while 9.9--24.1\\% of items change correctness state.')
replace('appendix.tex', r'\input{tables/failure_analysis.tex}', r'See \cref{tab:failures,tab:failure-analysis} for counts and archived examples.')
path = P / 'appendix.tex'; text = path.read_text()
a = text.index('The experimental matrix diagram'); b = text.index(r'\subsection{Audited task-level breakdown}')
text = text[:a] + r'''The experimental matrix (\cref{fig:matrix}) is drawn directly with TikZ
in the results source. Its prospective nested-factorial block follows
\texttt{configs/experiments/t4\_factorial.yaml}; it is not an executed
extension of the historical OFAT matrix.

''' + text[b:]; path.write_text(text)
replace('ranking.tex', r'\label{sec:sampling}', '\\label{sec:sampling}\n\\input{tables/sampling.tex}')
replace('ranking.tex', r'\label{sec:ranking}', '\\label{sec:ranking}\n\\input{tables/audited_ranking.tex}\n\\input{tables/audited_head_to_head.tex}')
replace('results.tex', r'\input{tables/main_results.tex}', r'\input{tables/audited_control.tex}')
replace('results.tex', r'\subsection{Quantization, backend, and sampling move scores little}', r'''\begin{figure}[tbp]
\centering
\includegraphics[width=0.72\linewidth]{prompt_forest.pdf}
\caption{Prompt-dependent extracted-answer accuracy with Wilson 95\% intervals.}
\label{fig:prompt}
\end{figure}
\input{tables/audited_sensitivity.tex}
\subsection{Quantization, backend, and sampling move scores little}''')


path = P / 'results.tex'; text = path.read_text()
a = text.index('The failure analysis covers'); b = text.index('The single Qwen2.5-7B cell')
text = text[:a] + r'''Across all 31 successful runs, including sampling and the single 7B cell,
24,800 output records contain 3 unparseable outputs and no empty outputs
(\cref{tab:failures}). These are repeated responses to 800 items, not
24,800 independent questions. An unparseable response is nonempty with a
null stored prediction; a parseable wrong prediction is a separate category.
Runtime failures outside successful archives are unknown.
\input{tables/audited_failures.tex}

\cref{tab:failure-analysis} provides selected, traceable examples of
numeric-format failure, refusal, off-target response, and extraction
mismatch. These examples do not estimate the prevalence of reasoning
errors or demonstration copying. In particular, the archived Phi five-shot
response explicitly answers C while the stored prediction is A and gold is C.
Rare null predictions therefore do not establish extractor validity.
The prompt-level task changes are consistent with sensitivity to answer
format, but a causal attribution of every error requires blinded review.

''' + text[b:]; path.write_text(text)
path = P / 'discussion.tex'; text = path.read_text()
a = text.index(r'\paragraph{Failure analysis implications.}'); b = text.index(r'\section{Threats to Validity and Limitations}')
text = text[:a] + r'''\paragraph{Failure analysis implications.}
The automated categories (\cref{tab:failures}) contain 3 unparseable and
11,175 parseable incorrect responses across 24,800 outputs, with no empty
outputs. This does not imply that parsing is harmless: the selected
extraction mismatch in \cref{tab:failure-analysis} shows that a correct
explicit answer may still be scored incorrectly. Counts of genuine reasoning
errors, demonstration copying, and extraction errors require independent
adjudication and are not inferred from the null-prediction rate.

''' + text[b:]; path.write_text(text)
print('Manuscript repair applied.')
