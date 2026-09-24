"""Read-only inventory of research inputs; writes a derived audit, never results."""
from __future__ import annotations
import ast
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {'.git', '.venv', 'node_modules', '__pycache__', 'dist', '.pytest_cache'}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    inventory = []
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or EXCLUDE.intersection(p.relative_to(ROOT).parts):
            continue
        if p.is_relative_to(ROOT / 'paper' / 'analysis'):
            continue
        b = p.read_bytes()
        rec = {'path': str(p.relative_to(ROOT)), 'bytes': len(b), 'sha256': sha(b)}
        if p.suffix in {'.py', '.md', '.tex', '.yaml', '.toml', '.tsx', '.ts', '.bib', '.json', '.jsonl', '.ipynb'}:
            text = b.decode('utf-8')
            rec['lines'] = len(text.splitlines())
            if p.suffix == '.py':
                tree = ast.parse(text)
                rec['definitions'] = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
            elif p.suffix == '.ipynb':
                nb = json.loads(text)
                rec['cells'] = [{'type': c['cell_type'], 'source': c.get('source'), 'execution_count': c.get('execution_count'), 'outputs': c.get('outputs', [])} for c in nb['cells']]
            elif p.suffix == '.jsonl':
                rows = [json.loads(l) for l in text.splitlines() if l.strip()]
                rec['rows'] = len(rows)
                rec['tasks'] = dict(collections.Counter(str(r.get('task')) for r in rows))
        inventory.append(rec)
    registry = [json.loads(l) for l in (ROOT / 'results/registry_paper.jsonl').read_text().splitlines() if l.strip()]
    runs = []
    for r in registry:
        if r.get('status') != 'ok':
            continue
        p = ROOT / r['path']; b = json.loads(p.read_text()); its = b['items']; m = b['manifest']
        runs.append({'run_id': r['run_id'], 'sha256': sha(p.read_bytes()), 'n': len(its), 'unique_ids': len({i['id'] for i in its}), 'correct': sum(i['correct'] for i in its), 'tasks': dict(collections.Counter(i['task'] for i in its)), 'manifest': m})
    archives = []
    for p in ROOT.parent.glob('*.zip'):
        with zipfile.ZipFile(p) as z:
            members = []
            for name in z.namelist():
                if name.endswith('/'):
                    continue
                local = ROOT / name
                members.append({'path': name, 'sha256': sha(z.read(name)), 'same_as_repository': sha(z.read(name)) == sha(local.read_bytes()) if local.is_file() else None})
            archives.append({'archive': p.name, 'members': members})
    git_objects = {}
    for commit in sorted({r['manifest'].get('git_commit') for r in runs} - {None}):
        git_objects[commit] = subprocess.run(['git', 'cat-file', '-e', commit + '^{commit}'], cwd=ROOT, capture_output=True).returncode == 0
    other_runs = []
    selected = {r['run_id'] for r in runs}
    for p in sorted((ROOT / 'results').rglob('*.json')):
        b = json.loads(p.read_text())
        if isinstance(b, dict) and 'items' in b and p.stem not in selected:
            other_runs.append({'path': str(p.relative_to(ROOT)), 'n': len(b['items']), 'settings': b.get('manifest', {}).get('settings', {})})
    import sys
    sys.path.insert(0, str(ROOT / 'src'))
    from apertus_eval_prep.scoring import is_correct, predicted
    frozen = {i['id']: i for i in [json.loads(l) for l in (ROOT / 'data/official/eval_set.jsonl').read_text().splitlines()]}
    for r in runs:
        b = json.loads((ROOT / 'results/runs' / (r['run_id'] + '.json')).read_text())
        r['frozen_ids_match'] = {i['id'] for i in b['items']} == set(frozen)
        r['gold_mismatches'] = [i['id'] for i in b['items'] if i['id'] not in frozen or str(i['gold']) != str(frozen[i['id']]['gold'])]
        r['rescoring_mismatches'] = [i['id'] for i in b['items'] if is_correct(i['task'], i['generation'], str(i['gold'])) != i['correct'] or predicted(i['task'], i['generation'], str(i['gold'])) != i['predicted']]
    output = {'recorded_git_objects_available': git_objects, 'other_run_artifacts': other_runs, 'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'files': inventory, 'paper_runs': runs, 'archives': archives}
    out = ROOT / 'paper/analysis/repository_inventory.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    print(f'Inventoried {len(inventory)} files; {len(runs)} paper runs; {len(archives)} archives.')
    for r in runs:
        print(r['run_id'], r['n'], r['correct'], r['manifest'].get('packages'))

if __name__ == '__main__':
    main()
