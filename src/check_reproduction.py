"""Replay captured facts in isolation and compare all deterministic exports."""

import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from verify_freeze import verify as verify_freeze
from verify_source import verify as verify_source
from verify_results import verify as verify_results

ROOT=Path(__file__).resolve().parents[1]


def main():
    frozen=verify_freeze(ROOT);source=verify_source(ROOT)
    fields=0;documents=0;phases=[]
    with tempfile.TemporaryDirectory(prefix='transit-replay-') as directory:
        target=Path(directory)
        for name in ['protocol.json','PROTOCOL.md','SOURCES.md','FREEZE.json']:
            shutil.copy2(ROOT/name,target/name)
        shutil.copytree(ROOT/'src',target/'src',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'data',target/'data')
        shutil.copytree(ROOT/'tests',target/'tests')
        (target/'results').mkdir()
        shutil.copy2(ROOT/'results/development-cohorts.csv',target/'results/development-cohorts.csv')
        verify_freeze(target)
        for phase in ['development','held']:
            subprocess.run([sys.executable,'src/run_analysis.py',phase],cwd=target,check=True,capture_output=True)
            result=verify_results(phase,target);phases.append(result)
        subprocess.run([sys.executable,'src/summarize.py'],cwd=target,check=True,capture_output=True)
        for original in sorted((ROOT/'results').glob('*.csv')):
            with original.open(encoding='utf-8',newline='') as left,(target/'results'/original.name).open(encoding='utf-8',newline='') as right:
                a=list(csv.reader(left));b=list(csv.reader(right))
            assert a==b,original.name
            fields+=sum(len(row) for row in a[1:])
        for phase,result in zip(['development','held'],phases):
            assert result==json.loads((ROOT/'results'/(phase+'-VERIFICATION.json')).read_text(encoding='utf-8'))
            documents+=1
        assert source==verify_source(target);documents+=1
    result=dict(status='PASS',exact_csv_fields=fields,verification_documents=documents,protected_dependencies=frozen['dependencies'],phases=phases,
                timing='Per-phase original execution timings retained; variable replay timings excluded from deterministic identity.')
    (ROOT/'REPRODUCTION_CHECK.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
