"""Generate a claim ledger linking active comparisons to raw experiment IDs."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'paper'

def main():
    a = json.loads((P/'analysis/audited_statistics.json').read_text())
    lines = ['# Claim audit — active manuscript', '', 'Supersedes prior claim audits. IDs resolve through results/registry_paper.jsonl to raw outputs. Arithmetic confidence does not authenticate inference or semantic scoring. Numerical prose still needs human review.', '', '| Claim | Evidence | File | Experiment ID | Figure/Table | Confidence |', '|---|---|---|---|---|---|']
    for r in a['head_to_head']:
        lines.append(f"| Qwen-minus-Phi under {r['config']}: {r['delta_pp']:+.3f} pp | Paired counts, exact conditional test, stratified CI; Holm family of eight | analysis/audited_statistics.json | {r['phi_id']}; {r['qwen_id']} | audited_head_to_head; audited_ranking | High arithmetic; conditional exploratory inference |")
    for claim, evidence in [('Prompt range exceeds control model gap','139/800 versus 21/800; selected configurations only'),('No backend/quantization rejection at Holm 0.05','All relevant adjusted p values in contrasts; not equivalence'),('Greedy correctness vectors match','Zero discordant outcomes in seed contrasts; not text identity'),('Failure denominator retains archived outputs','All successful registry runs including sampled and single-cell; unarchived failures unknown'),('Historical inference and isolated effects unavailable','Unpinned revisions, software drift and incomplete effective settings'),('ERS and factorial claims omitted','Tooling/plans are not empirical validation')]:
        lines.append(f'| {claim} | {evidence} | analysis/audited_statistics.json; analysis/run_details.json; REPOSITORY_AUDIT.md | Per-entry run_id/control_id; no confirmatory run IDs | Active results/limitations and audited tables | Descriptive or explicitly NOT SUPPORTED |')
    (P/'CLAIM_AUDIT.md').write_text('\n'.join(lines)+'\n')

if __name__ == '__main__': main()
