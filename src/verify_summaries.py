"""Independently rebuild every displayed/full-grid summary from checked row exports."""

import csv
from fractions import Fraction as Q
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def verify(root=ROOT):
    checks=0
    def read(name):
        with (Path(root)/'results'/name).open(encoding='utf-8',newline='') as stream:return list(csv.DictReader(stream))
    for phase in ['development','held']:
        points=read(phase+'-points.csv');bounds=read(phase+'-bounds.csv')
        for kind in ['setting-summary','primary-summary']:
            rows=read(phase+'-'+kind+'.csv')
            assert len(rows)==(81 if kind=='setting-summary' else 12)
            seen=set()
            for row in rows:
                if kind=='setting-summary':
                    key=tuple(row[k] for k in ['fraction','ranking','masked_side','view'])
                    sample=[p for p in points if tuple(p[k] for k in ['fraction','ranking','masked_side','view'])==key]
                else:
                    key=(row['year'],row['view'])
                    sample=[p for p in points if p['fraction']=='1/10' and p['ranking']=='baseline_volume_desc' and p['masked_side']=='prior' and p['view']==row['view'] and (row['year']=='ALL' or p['year']==row['year'])]
                assert key not in seen;seen.add(key)
                errors=[];wrong=false=missed=0
                for p in sample:
                    if p['growth']=='' or p['truth_growth']=='':continue
                    value,truth=Q(p['growth']),Q(p['truth_growth']);errors.append(100*(value-truth))
                    wrong+=int((value>0)-(value<0)!=(truth>0)-(truth<0))
                    false+=int(value>0 and truth<=0);missed+=int(value<=0 and truth>0)
                n=len(errors)
                expected=dict(n=str(n),undefined=str(len(sample)-n),mae_pp='' if not n else str(sum(map(abs,errors))/n),mse_pp='' if not n else str(sum(x*x for x in errors)/n),sign_errors=str(wrong),false_growth=str(false),missed_growth=str(missed))
                for field,value in expected.items():assert row[field]==value,(phase,kind,key,field)
                checks+=len(row)
        rows=read(phase+'-bound-summary.csv');assert len(rows)==9
        seen=set()
        for row in rows:
            key=(row['gamma'],row['masked_side']);assert key not in seen;seen.add(key)
            sample=[b for b in bounds if (b['gamma'],b['masked_side'])==key]
            expected=dict(n=str(len(sample)),finite=str(sum(b['state']=='finite' for b in sample)),assumptions_valid=str(sum(int(b['violated_components'])==0 for b in sample)),
                          truth_contained=str(sum(b['lower']!='' and Q(b['lower'])<=Q(b['truth_growth']) and (b['upper']=='' or Q(b['truth_growth'])<=Q(b['upper'])) for b in sample)),
                          violated_components=str(sum(int(b['violated_components']) for b in sample)),conditional_positive_lowers=str(sum(b['lower']!='' and Q(b['lower'])>0 for b in sample)),
                          assumption_supported_positive=str(sum(b['lower']!='' and Q(b['lower'])>0 and b['violated_components']=='0' for b in sample)))
            for field,value in expected.items():assert row[field]==value,(phase,key,field)
            checks+=len(row)
    return dict(status='PASS',exact_summary_scalar_checks=checks,scope='Every setting, primary and bound summary independently recomputed from row-level growth and interval exports.')


if __name__=='__main__':
    result=verify();(ROOT/'results/SUMMARY_VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
