"""Regression tests for the manuscript-specific analysis (no inference)."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audited_analysis import paired
from validate_paper import active_sources, finite
from paper_common import load_paper_data


def records(values):
    return [{'id': str(i), 'task': 'task', 'gold': 'A', 'correct': v} for i, v in enumerate(values)]


def test_exact_mcnemar_known_small_sample():
    r = paired(records([False]*8), records([True]*8), n_boot=100)
    assert r['p_exact'] == 2/256
    assert r['delta_pp'] == 100
    assert r['ci95_pp'] == [100, 100]


def test_identical_and_balanced_pairs():
    a = records([True, False, True, False])
    assert paired(a, a, n_boot=100)['ci95_pp'] == [0, 0]
    assert paired(a, a, n_boot=100)['p_exact'] == 1
    assert paired(a, records([False, True, False, True]), n_boot=100)['p_exact'] == 1


def test_pairing_is_order_invariant_and_seeded():
    a = records([True, False, True, False])
    b = records([True, True, False, False])
    assert paired(a,b) == paired(list(reversed(a)),b)


def test_pairing_rejects_duplicate_missing_and_nonboolean():
    a = records([True, False])
    for b in (a[:1], [a[0],a[0]], records([1, False])):
        with pytest.raises(ValueError): paired(a, b)


def test_paper_accuracy_uses_counts_not_rounded_artifacts():
    data = load_paper_data()
    assert not data['problems']
    q = data['cells'][('Qwen/Qwen2.5-3B-Instruct','control','control')]
    assert q['overall']['accuracy'] == q['overall']['correct']/q['overall']['n']
    assert q['overall']['accuracy'] == 515/800


def test_recursive_tex_inputs_and_missing_files(tmp_path):
    (tmp_path/'main.tex').write_text('\\input{section}\n% \\input{ignored}\n')
    with pytest.raises(FileNotFoundError): active_sources(tmp_path)
    (tmp_path/'section.tex').write_text('hello')
    assert len(active_sources(tmp_path)) == 2
    (tmp_path/'section.tex').write_text('\\input{main}')
    with pytest.raises(ValueError, match='cyclic'): active_sources(tmp_path)


@pytest.mark.parametrize('value', [float('nan'),float('inf'),-float('inf')])
def test_no_nonfinite_numbers(value):
    with pytest.raises(ValueError): finite({'nested':[value]})
