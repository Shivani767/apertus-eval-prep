import type { SiteData } from "../data"

/** Methodology, threats, limitations — concise, linking to repo docs. */
export function Method({ site }: { site: SiteData }) {
  const docs: [string, string, string][] = [
    ["Research audit & plan", "Architecture, entry points, implemented-vs-planned, research questions.", "docs/RESEARCH_AUDIT.md · docs/RESEARCH_PLAN.md"],
    ["Statistical methodology", "Bootstrap CIs, permutation tests, McNemar, Holm/BH, ANOVA notes.", "docs/STATISTICAL_METHODOLOGY.md · docs/STATISTICAL_METHODOLOGY_APPENDIX.md"],
    ["Evaluation cost", "Cost model: MEASURED vs DERIVED vs UNAVAILABLE labels, zero-fill ban.", "docs/EVALUATION_COST.md"],
    ["Metamorphic evaluation", "Prompt-robustness transforms and the EvalFrag seed schema.", "docs/METAMORPHIC_EVAL.md"],
    ["Run status", "Live matrix status: which cells are done, pending, or deviating.", "paper/run_status.md"],
  ]
  return (
    <div>
      <h2>Methodology &amp; limitations</h2>
      <h3>Controlled OFAT design</h3>
      <p className="note">
        One factor varies at a time around a fixed control (HF backend, default prompt,
        fp-none, seed 0, greedy decoding), plus a temperature-0.7 sampling arm with three
        seeds. The planned matrix is defined in <code>configs/experiments/stability.yaml</code> (t4
        profile: {site.coverage.planned_cells ?? "?"} cells); coverage on this site is recomputed
        from that file, so it can never go stale.
      </p>
      <h3>Models &amp; tasks</h3>
      <p className="note">
        {site.models.map((m) => m.label).join(", ")} · tasks arc_easy, gsm8k, hellaswag, mgsm
        (frozen official slice; paraphrase arm skipped on this profile).
      </p>
      <h3>Metrics &amp; failure taxonomy</h3>
      <p className="note">
        Generative exact-match accuracy with Wilson 95% CIs; per-item outcomes in five
        mutually exclusive categories (correct, wrong_answer, unparseable, empty_output,
        runtime_error). Latency/throughput shown only where the artifact measured them.
      </p>
      <h3>Threats to validity</h3>
      <ul className="note">
        <li>Single hardware family (Tesla T4, Colab) — backend/latency numbers do not generalize to other GPUs.</li>
        <li>Small model set (1.7B–3.8B); 7B has one cell. No claim is made about larger models.</li>
        <li>OFAT design cannot detect factor interactions; a factorial extension exists but is unused here.</li>
        <li>ERS is provisional and descriptive; the ablation on the Reliability page shows its weight sensitivity.</li>
        <li>{site.reproducibility.n_fail} sampled cell(s) currently fail artifact verification — excluded from paper claims until re-verified.</li>
      </ul>
      <h3>Full documentation</h3>
      <div className="table-wrap"><table className="data"><tbody>
        {docs.map(([t, d, p]) => <tr key={t}><td><strong>{t}</strong></td><td className="note">{d}<br /><code>{p}</code></td></tr>)}
      </tbody></table></div>
      <h3>Research artifact</h3>
      <p className="note">
        Repository <a href="https://github.com/Shivani767/apertus-eval-prep">github.com/Shivani767/apertus-eval-prep</a> ·
        registry <code>{site.registry}</code> · paper sources in <code>paper/</code> ·
        reproduce with <code>python -m apertus_eval_prep reproduce …</code> (see Reproducibility).
      </p>
    </div>
  )
}
