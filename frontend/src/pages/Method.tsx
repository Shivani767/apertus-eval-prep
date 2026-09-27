import type { SiteData } from "../data"

/** Methodology, threats, limitations — concise, linking to repo docs. */
export function Method({ site }: { site: SiteData }) {
  const docs: [string, string, string][] = [
    ["Evidence and claim boundaries", "What MOCK, real-model, human-reviewed, and production evidence each support — and what they do not.", "docs/METHODOLOGY.md#evidence-and-claim-boundaries"],
    ["Final audit & release report", "Repository audit, hygiene findings, validation results, known limitations.", "docs/FINAL_AUDIT.md · docs/FINAL_RELEASE_REPORT.md"],
    ["CLI reference", "All 30 commands with verified options; no documented command is hypothetical.", "docs/CLI_REFERENCE.md"],
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
      <h3>Evidence and claim boundaries</h3>
      <p className="note">
        Every number on this dashboard belongs to one evidence tier. The tier is part of the
        claim, so it is stated here rather than left to the reader.
      </p>
      <ul className="note">
        <li>
          <strong>What this dashboard shows.</strong> The controlled OFAT research registry{" "}
          <code>{site.registry}</code> — {site.models.length} models,{" "}
          {site.cells.length} committed configurations, real open-weight models on a Tesla T4.
          This is experimental real-model evidence, specific to the recorded model revision,
          tokenizer, task slice, prompt, decoding, backend, quantization, and hardware.
        </li>
        <li>
          <strong>It is not a production benchmark.</strong> Latency and throughput are
          client-side wall-clock measurements on one ephemeral accelerator. They are not
          serving latency, and they say nothing about throughput, tail latency, or cost at
          scale.
        </li>
        <li>
          <strong>The provenance legend is a research label, not an evidence mode.</strong>{" "}
          MEASURED / SAMPLED / DERIVED / PENDING describe how a number reached this page. The
          platform's machine-checked evidence modes (MOCK, SYNTHETIC, LOCAL_REAL_MODEL,
          EXTERNAL_PROVIDER, HARDWARE_MEASURED, HUMAN_VALIDATED, MIXED, UNKNOWN) are defined
          in <code>docs/METHODOLOGY.md</code> and are attached to the newer typed-platform
          artifacts; the registry rendered here predates them, so a cell labelled MEASURED
          here has not been machine-verified against an evidence mode.
        </li>
        <li>
          <strong>No safety claim.</strong> This dashboard contains no safety evaluation, and
          nothing here certifies that any model is safe. The repository's red-team safety
          suite is an evaluation over a declared taxonomy, not a certification.
        </li>
        <li>
          <strong>No human validation.</strong> No completed human-review artifacts back any
          number here. Where the repository ships annotation tooling, it ships templates, not
          evidence that review occurred.
        </li>
        <li>
          <strong>Findings do not generalize beyond their configuration.</strong> Each
          statement here is about the recorded model plus prompt plus decode plus backend
          plus hardware. It is not a claim about the model alone, nor about models outside
          this matrix.
        </li>
      </ul>
      <h3>Where the newer evidence lives</h3>
      <p className="note">
        This dashboard renders the original OFAT research registry. The typed evaluation
        platform (Phases 1–8) produces a separate curated evidence set — real open-weight
        models scored on shared core, RAG/agent, and safety suites, with declared evidence
        modes — published under <code>results/colab_real_model/</code> with one directory per
        model and a <code>summary.md</code> whose warnings should be read before quoting any
        figure. Runs that produced no usable measurement are kept separately under{" "}
        <code>results/colab_failed_runs/</code> and are excluded from every comparison.
      </p>
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
