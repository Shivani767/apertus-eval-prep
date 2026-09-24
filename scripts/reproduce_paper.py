"""Regenerate and validate stored-output analyses; clean-source LaTeX build.

No model inference. --analyze-only omits compilation. The submission-source
bundle contains only active TeX dependencies, bibliography and figures.
"""
from __future__ import annotations
import argparse
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent

def compile_paper():
    from validate_paper import active_sources
    paper = REPO / 'paper'
    with tempfile.TemporaryDirectory(prefix='apertus-clean-tex-') as tmp:
        root = Path(tmp)
        files = active_sources()
        for p in files:
            dest = root / p.relative_to(paper)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
        shutil.copy2(paper/'references.bib', root/'references.bib')
        text = '\n'.join(files.values())
        for fig in re.findall(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}', text):
            dest = root/'figures'/fig
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paper/'figures'/fig, dest)
        # Save an asset-only source bundle before compilation adds intermediates.
        shutil.make_archive(str(paper/'arxiv-source'), 'gztar', root)
        if shutil.which('tectonic'):
            commands = [['tectonic', '--keep-logs', '--keep-intermediates', 'main.tex']]
        elif shutil.which('pdflatex') and shutil.which('bibtex'):
            latex = ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'main.tex']
            commands = [latex, ['bibtex','main'], latex, latex]
        else:
            raise RuntimeError('Install Tectonic or PDFLaTeX plus BibTeX; analysis succeeded, PDF not built')
        logs = []
        for cmd in commands:
            result = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            logs.append(result.stdout)
            (paper/'analysis/build.log').write_text('\n'.join(logs))
            if result.returncode:
                raise RuntimeError('LaTeX failed; see paper/analysis/build.log')
        final_log = (root/'main.log').read_text(errors='replace')
        (paper/'analysis/latex-final.log').write_text(final_log)
        if re.search(r'undefined references|Citation .* undefined|multiply defined|Overfull \\[hv]box', final_log):
            raise RuntimeError('Unresolved citations/references, duplicate labels or overflow; see latex-final.log')
        shutil.copy2(root/'main.pdf', paper/'main.pdf')
        if (root/'main.bbl').exists(): shutil.copy2(root/'main.bbl', paper/'main.bbl')
        print('Clean-source LaTeX build OK; paper/main.pdf and paper/arxiv-source.tar.gz')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analyze-only', action='store_true')
    args = parser.parse_args()
    versions = {'python': sys.version.split()[0]}
    for module in ('numpy', 'matplotlib', 'yaml'):
        imported = importlib.import_module(module)
        versions[module] = getattr(imported, '__version__', 'not recorded')
    os.environ['SOURCE_DATE_EPOCH'] = '0'
    os.environ['MPLBACKEND'] = 'Agg'
    for name in ('statistical_analysis', 'audited_analysis', 'generate_figures', 'validate_paper'):
        cmd = [sys.executable, f'scripts/{name}.py']
        print('+', ' '.join(cmd), flush=True)
        subprocess.run(cmd, cwd=REPO, check=True)
    (REPO/'paper/analysis/analysis_environment.json').write_text(json.dumps(versions, indent=2)+'\n')
    if not args.analyze_only:
        compile_paper()
    print('reproduce_paper: OK (stored outputs only; not historical inference reproduction)')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

