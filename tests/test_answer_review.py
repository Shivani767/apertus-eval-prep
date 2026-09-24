"""Review export tests; fixtures are software tests, not experimental results."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from export_answer_review import CONFIGS, MODELS, make_packet


def fixture_data():
    frozen = [{'id': str(i), 'task': 'math', 'gold': '2', 'language': 'en',
               'prompt': 'What is one plus one?'} for i in range(3)]
    data = {'problems': [], 'cells': {}, 'blobs': {}}
    for m in MODELS:
        for f, l in CONFIGS:
            run = f'{m}/{f}/{l}'
            data['cells'][(m, f, l)] = {'run_id': run}
            data['blobs'][run] = {'items': [dict(r, generation='2', predicted='2', correct=True) for r in frozen]}
    return data, frozen


def test_review_export_hides_labels_and_preserves_outputs():
    data, frozen = fixture_data()
    rows, key = make_packet(data, frozen, per_task=2)
    assert len(rows) == 8
    assert key['status'] == 'UNREVIEWED'
    assert len(key['mapping']) == len(rows)
    allowed = {'review_id', 'task', 'language', 'question', 'generation',
               'answer_status', 'intended_answer', 'notes'}
    for row in rows:
        assert set(row) == allowed
        assert row['generation'] == '2'
        assert row['answer_status'] == row['intended_answer'] == row['notes'] == ''
        assert key['mapping'][row['review_id']]['stored_correct'] is True
    _, other = make_packet(data, frozen, per_task=2)
    assert key['selected_item_ids'] == other['selected_item_ids']
    assert set(key['mapping']).isdisjoint(other['mapping'])


def test_review_export_rejects_invalid_size_and_missing_coverage():
    data, frozen = fixture_data()
    for size in (0, -1, 4):
        with pytest.raises(ValueError):
            make_packet(data, frozen, per_task=size)
    next(iter(data['blobs'].values()))['items'].pop()
    with pytest.raises(ValueError, match='coverage'):
        make_packet(data, frozen, per_task=1)
