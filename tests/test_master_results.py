"""Check each generated master-table row against archived counts and statistics."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from paper_common import load_paper_data, SHORT_MODEL
from apertus_eval_prep.stats import wilson_interval


def test_master_table_matches_all_archived_cells():
    data = load_paper_data()
    assert not data['problems']
    audit = json.loads((ROOT / 'paper/analysis/audited_statistics.json').read_text())
    text = (ROOT / 'paper/tables/master_results.tex').read_text()
    contrasts = {r['run_id']: r for r in audit['contrasts']}
    rows = [line for line in text.splitlines()
            if any(line.startswith(m + ' & ') for m in SHORT_MODEL.values())]
    assert len(rows) == 32  # 31 measured rows plus explicit missing-cell row
    for record, line in zip(data['rows'], rows[:31]):
        cols = [s.strip() for s in line.removesuffix(r'\\').split('&')]
        assert len(cols) == 6
        model, config, accuracy, interval, delta, pvalue = cols
        assert model == SHORT_MODEL[record['model_id']]
        level = str(record['factor_level']).replace('_', r'\_')
        expected_label = 'control' if record['factor'] == 'control' else level
        if record['factor'] == 'seed':
            expected_label = 'greedy seed ' + level
        assert config == expected_label
        score = record['overall']
        n, k = score['n'], score['correct']
        assert accuracy == f'{100*k/n:.3f}'
        assert 0 <= float(accuracy) <= 100
        lo, hi = wilson_interval(k, n)
        assert interval == f'[{100*lo:.2f}, {100*hi:.2f}]'
        contrast = contrasts.get(record['run_id'])
        if contrast is None:
            assert delta == pvalue == '---'
        else:
            assert delta == f"{contrast['delta_pp']:+.3f}"
            p = contrast['p_holm']
            assert pvalue == (f'{p:.3g}' if p >= .001 else '$<0.001$')
    assert '3 planned cells: not run' in rows[-1]
    assert 'Phi-3.5-mini' in rows[-1]
