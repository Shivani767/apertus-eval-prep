"""Post-hoc math-parser sensitivity on stored runs; NOT held-out validation.

Keeps all math records in denominator, preserves historical scores and writes
an exclusive new report. No inference or assertion of human answer accuracy.
"""
import argparse
import hashlib
import json
from pathlib import Path

from paper_common import REPO_ROOT, load_paper_data
from apertus_eval_prep.strict_scoring import PARSER_ID, extract_final_line_number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    data = load_paper_data()
    if data['problems']:
        raise ValueError(data['problems'])
    summaries, records = [], []
    for row in data['rows']:
        blob = data['blobs'][row['run_id']]
        for task in ('gsm8k', 'mgsm'):
            items = [i for i in blob['items'] if i['task'] == task]
            if not items:
                raise ValueError(f'missing task {task}')
            old_count = strict_count = accepted = changed = 0
            for item in items:
                answer = extract_final_line_number(item['generation'])
                strict_correct = answer is not None and answer == str(item['gold']).strip()
                old_count += item['correct']
                strict_count += strict_correct
                accepted += answer is not None
                changed += answer != item['predicted']
                records.append({'run_id': row['run_id'], 'item_id': item['id'],
                                'task': task, 'historical_prediction': item['predicted'],
                                'strict_prediction': answer, 'gold': item['gold'],
                                'historical_correct': item['correct'],
                                'strict_correct': strict_correct})
            summaries.append({'run_id': row['run_id'], 'model': row['model_id'],
                              'factor': row['factor'], 'level': row['factor_level'],
                              'task': task, 'n': len(items),
                              'historical_correct': old_count, 'strict_correct': strict_count,
                              'accepted': accepted, 'rejected': len(items) - accepted,
                              'changed_predictions': changed,
                              'delta_pp': 100 * (strict_count - old_count) / len(items)})
    sources = [REPO_ROOT / r['path'] for r in data['rows']]
    sources += [Path(__file__), REPO_ROOT / 'src/apertus_eval_prep/strict_scoring.py']
    report = {'status': 'EXPLORATORY_POST_HOC_NOT_HELD_OUT', 'parser_id': PARSER_ID,
              'warning': 'Rejections reflect strict format mismatch, not adjudicated semantic errors. No significance or ranking-validity claim.',
              'source_sha256': {str(p.relative_to(REPO_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              'summaries': summaries, 'records': records}
    with args.out.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')
    print(f'Wrote {len(records)} post-hoc math rescoring records; {len(summaries)} run/task summaries. Historical results unchanged.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
