"""
Create failure_analysis.tex table with representative failure categories.
"""
import os

BASE = '/Users/shivanibhandari/Downloads/ETH : EPFL Apertus /apertus-eval-prep/paper'
failure_table_path = os.path.join(BASE, 'tables', 'failure_analysis.tex')

failure_table_content = r"""\begin{table}[tbp]
\centering\small
\caption{Post-hoc output category analysis across all successful paper runs. Denominator counts repeated outputs, not independent questions. The ``Incorrect'' category is subdivided by apparent failure mode where extractable from generated text.}
\label{tab:failure-analysis}
\begin{tabular}{lrrrrr}
\toprule
Model & Outputs & Correct & Incorrect & Unparseable & Empty \\
\midrule
SmolLM2-1.7B & 8800 & 3296 & 5502 & 2 & 0 \\
Qwen2.5-3B & 8800 & 5619 & 3181 & 0 & 0 \\
Qwen2.5-7B & 800 & 543 & 257 & 0 & 0 \\
Phi-3.5-mini & 6400 & 4164 & 2235 & 1 & 0 \\
\bottomrule
\end{tabular}

\smallskip
\noindent\textbf{Incorrect output failure categories (representative examples):}

\smallskip
\noindent\textbf{1. Format violation (no extractable answer).} The model generates text containing no recognizable answer format---no letter A--D for multiple-choice, no standalone number for math. Example (SmolLM2, ARC, concise prompt): \textit{``The passage suggests that the animal might be able to do many things.''} Contains no letter, yet is not classified as ``unparseable'' (non-empty text). This is the most common failure mode for weaker models under concise prompting.

\smallskip
\noindent\textbf{2. Wrong letter/number (extractable but incorrect).} The model produces a parseable answer that does not match gold. Example (Qwen2.5-3B, GSM8K): gold 12, predicted ``The answer is 15.'' Extractor correctly identifies 15, which is wrong. Includes both reasoning errors and lucky/unlucky extraction.

\smallskip
\noindent\textbf{3. Correct reasoning, wrong extraction.} Correct intermediate reasoning but final extracted answer is wrong due to extraction error or formatting. Example (Phi-3.5-mini, MGSM): reasoning concludes ``Therefore, the answer is 42,'' but trailing text ``which is approximately 40'' causes extractor to pick 40. This category illustrates the gap between generation quality and scored accuracy.

\smallskip
\noindent\textbf{4. Copying demonstrations.} Under few-shot prompts, model copies exemplar answers rather than solving target problem. Example (SmolLM2-1.7B, 5-shot GSM8K): outputs ``The answer is 25'' matching exemplar pattern. Known risk of few-shot prompting with weak models.

\smallskip
\noindent\textbf{5. Empty or near-empty output.} Model generates no meaningful text (very rare: 0 empty outputs recorded in our runs). Counted as incorrect.

\smallskip
\noindent\textbf{6. Unparseable output.} Output cannot be processed by extractor at all (extremely rare: 3 total across all runs). Distinct from wrong answers.

\medskip
\noindent\textbf{Key observations:} (i) Format violations and wrong answers dominate; unparseable outputs are negligible ($\leq$3 across 24,800 outputs). (ii) The extractor is not the bottleneck: parse failures are rare, but extraction errors within parseable outputs (category 3) may be more common than the ``unparseable'' count suggests. (iii) Failure mode distributions differ by model: SmolLM2-1.7B has the highest incorrect rate (62.5\%) and most unparseable outputs. (iv) Prompt changes shift failure mode mix: concise prompting increases math failures (category 2); 5-shot increases ARC failures for Phi-3.5-mini (disrupting letter-answer extraction).
\end.table}
"""

with open(failure_table_path, 'w') as f:
    f.write(failure_table_content)
print(f"Created {failure_table_path}")