"""Validate active TeX dependencies and deterministically regenerated analysis/assets.

No guarantee about arbitrary prose or scientific validity. Compilation is a
separate reproduction step. Uses existing generators in a temporary output tree;
never repairs stale outputs while validating them.
"""
from __future__ import annotations
import json
import math
import re
import tempfile
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
import io
from paper_common import REPO_ROOT, load_paper_data

PAPER = REPO_ROOT / 'paper'

def finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('non-finite numerical artifact')
    if isinstance(value, dict):
        for v in value.values(): finite(v)
    if isinstance(value, list):
        for v in value: finite(v)

def active_sources(paper=PAPER):
    files, visiting = {}, set()
    def walk(path):
        path = path.resolve()
        if not path.is_relative_to(paper.resolve()):
            raise ValueError('external TeX input')
        if path in visiting:
            raise ValueError('cyclic TeX input')
        if path in files: return
        visiting.add(path)
        text = re.sub(r'(?<!\\)%[^\n]*', '', path.read_text())
        files[path] = text
        for inc in re.findall(r'\\input\{([^}]+)\}', text):
            walk(paper / (inc if inc.endswith('.tex') else inc + '.tex'))
        visiting.remove(path)
    walk(paper / 'main.tex')
    return files

def validate():
    import audited_analysis as analysis
    import generate_figures as figures
    import statistical_analysis as descriptive
    files = active_sources()
    text = '\n'.join(files.values())
    if '/Users/' in text or '/home/' in text:
        raise ValueError('absolute local path in manuscript')
    keys = re.findall(r'@\w+\{([^,]+),', (PAPER / 'references.bib').read_text())
    if len(keys) != len(set(keys)): raise ValueError('duplicate bibliography key')
    cites = {k.strip() for group in re.findall(r'\\cite\w*(?:\[[^]]*\])*\{([^}]+)\}', text) for k in group.split(',')}
    if cites - set(keys): raise ValueError(f'missing citations: {cites-set(keys)}')
    labels = re.findall(r'\\label\{([^}]+)\}', text)
    if len(labels) != len(set(labels)): raise ValueError('duplicate active label')
    refs = {r.strip() for group in re.findall(r'\\(?:[Cc]ref|ref|eqref)\{([^}]+)\}', text) for r in group.split(',')}
    if refs-set(labels): raise ValueError(f'unresolved labels: {refs-set(labels)}')
    for fig in re.findall(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}', text):
        if not (PAPER / 'figures' / fig).is_file(): raise ValueError(f'missing figure: {fig}')
    data = load_paper_data()
    if data['problems']: raise ValueError(data['problems'])
    for name in ('statistics.json', 'audited_statistics.json', 'run_details.json'):
        finite(json.loads((PAPER / 'analysis' / name).read_text()))
    with tempfile.TemporaryDirectory(prefix='paper-validation-') as tmp:
        root = Path(tmp); (root/'analysis').mkdir(); (root/'tables').mkdir(); (root/'figures').mkdir()
        with redirect_stdout(io.StringIO()):
            with patch.object(descriptive, 'OUT_DIR', root/'analysis'):
                descriptive.main()
            with patch.object(analysis, 'OUT', root/'analysis'), patch.object(analysis, 'TABLES', root/'tables'):
                analysis.main()
            with patch.object(figures, 'STATS', root/'analysis/statistics.json'), patch.object(figures, 'OUT', root/'figures'):
                figures.main()
        for folder in ('analysis', 'tables', 'figures'):
            for generated in (root/folder).iterdir():
                target = PAPER / folder / generated.name
                if not target.exists() or target.read_bytes() != generated.read_bytes():
                    raise ValueError(f'stale or altered generated artifact: {folder}/{generated.name}')
    print(f'validate_paper: OK; {len(files)} active TeX inputs, {len(cites)} citations; raw-to-analysis-to-asset regeneration matches')

def main():
    try:
        validate()
    except (ValueError, KeyError, FileNotFoundError, AssertionError) as exc:
        print(f'VALIDATION FAILED: {exc}')
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

