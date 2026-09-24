"""Regenerate the master table using the canonical audited paper pipeline."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
from audited_analysis import render_master
from paper_common import load_paper_data

if __name__ == '__main__':
    data = load_paper_data()
    if data['problems']:
        raise ValueError(data['problems'])
    audit = json.loads((ROOT / 'paper/analysis/audited_statistics.json').read_text())
    render_master(data, audit)
    print('Master table regenerated using audited_analysis.render_master')
