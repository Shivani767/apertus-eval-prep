"""Synthetic contract tests, not empirical parser-validation evidence."""
import pytest
from apertus_eval_prep.strict_scoring import extract_final_line_number


@pytest.mark.parametrize('text,answer', [
    ('2 + 2 = 4\n4', '4'), ('\n  -12.50 \n\n', '-12.5'),
    ('+100', '100'), ('-0.0', '0'), ('.5', '0.5'),
    ('9007199254740993', '9007199254740993'),
])
def test_accepts_standalone_final_number(text, answer):
    assert extract_final_line_number(text) == answer


@pytest.mark.parametrize('text', [
    '', '  ', 'Da jeder Container 5 Autos enthält, teilen wir die Anzahl der zusätz',
    'The result is 4 containers.', '4\nBut this calculation is incomplete',
    'Final: 4', '4 or 5', '1,000', '4,5', '1e3', 'NaN', 'Infinity',
    '$4$', r'\boxed{4}',
])
def test_rejects_noncontract_output_without_fallback(text):
    assert extract_final_line_number(text) is None
