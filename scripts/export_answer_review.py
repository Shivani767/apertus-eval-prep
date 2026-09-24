"""Export a label-blinded, task-stratified answer-extraction review packet.

No inference, scoring changes, or human judgments. Output must not exist.
Give reviewers ONLY reviewer.jsonl and the protocol, never PRIVATE_key.json.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random
import uuid

from paper_common import REPO_ROOT, load_paper_data

MODELS = ('Qwen/Qwen2.5-3B-Instruct', 'microsoft/Phi-3.5-mini-instruct')
CONFIGS = (('control', 'control'), ('prompt_id', '5shot'))


def make_packet(data, frozen, per_task=20, seed=0):
    if per_task < 1:
        raise ValueError('per_task must be positive')
    if data['problems']:
        raise ValueError(data['problems'])
    refs = {r['id']: r for r in frozen}
    if len(refs) != len(frozen) or not refs:
        raise ValueError('frozen IDs must be unique and nonempty')
    runs = []
    for model in MODELS:
        for factor, level in CONFIGS:
            cell = data['cells'][(model, factor, level)]
            items = data['blobs'][cell['run_id']]['items']
            indexed = {i['id']: i for i in items}
            if len(indexed) != len(items) or set(indexed) != set(refs):
                raise ValueError('run/frozen coverage mismatch')
            runs.append((cell['run_id'], model, factor, level, indexed))
    rng = random.Random(seed)
    selected = []
    for task in sorted({r['task'] for r in frozen}):
        candidates = sorted(k for k, r in refs.items() if r['task'] == task)
        if per_task > len(candidates):
            raise ValueError(f'per_task exceeds available items for {task}')
        selected.extend(rng.sample(candidates, per_task))
    rows, key = [], {}
    for item_id in selected:
        ref = refs[item_id]
        for run_id, model, factor, level, indexed in runs:
            item = indexed[item_id]
            if item['task'] != ref['task'] or str(item['gold']) != str(ref['gold']):
                raise ValueError('run/frozen metadata mismatch')
            # Independent opaque IDs: seed alone must not reveal model labels.
            review_id = uuid.uuid4().hex
            rows.append({'review_id': review_id, 'task': ref['task'],
                         'language': ref['language'], 'question': ref['prompt'],
                         'generation': item['generation'],
                         'answer_status': '', 'intended_answer': '', 'notes': ''})
            key[review_id] = {'run_id': run_id, 'model': model, 'factor': factor,
                              'level': level, 'item_id': item_id, 'gold': ref['gold'],
                              'stored_prediction': item['predicted'],
                              'stored_correct': item['correct'],
                              'generation_sha256': hashlib.sha256(item['generation'].encode()).hexdigest()}
    rng.shuffle(rows)
    return rows, {'status': 'UNREVIEWED', 'sampling_seed': seed,
                  'per_task': per_task, 'selected_item_ids': selected,
                  'review_records': len(rows), 'mapping': key}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--per-task', type=int, default=20)
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
    frozen_path = REPO_ROOT / 'data/official/eval_set.jsonl'
    frozen = [json.loads(line) for line in frozen_path.read_text().splitlines() if line.strip()]
    data = load_paper_data()
    rows, key = make_packet(data, frozen, args.per_task, args.seed)
    key['sources_sha256'] = {str(frozen_path.relative_to(REPO_ROOT)): hashlib.sha256(frozen_path.read_bytes()).hexdigest()}
    selected_runs = {r['run_id'] for r in key['mapping'].values()}
    for row in data['rows']:
        if row['run_id'] in selected_runs:
            path = Path(row['path'])
            path = path if path.is_absolute() else REPO_ROOT / path
            key['sources_sha256'][str(path.relative_to(REPO_ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'reviewer.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
    private = args.out / 'PRIVATE_key.json'
    private.write_text(json.dumps(key, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    private.chmod(0o600)
    print(f'Exported {len(rows)} UNREVIEWED records. Keep PRIVATE_key.json from reviewers. No results changed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
