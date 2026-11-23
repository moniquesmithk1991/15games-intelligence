#!/usr/bin/env python3
"""Create a non-destructive historical master candidate after guarded validation."""
import csv, hashlib, json
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
MASTER=ROOT/'historical_matches.csv'
ADD=ROOT/'data/merge_review/candidate_additions.csv'
OUT=ROOT/'data/merge_review'
EXPECTED='6362ddff48c453989d2416b8c16a4889641f1db4a4ae27d441203c5570fef55d'
FIELDS=['date','league','home','away','home_goals','away_goals']
def key(r):
    return (r['date'].strip(),r['league'].strip().upper(),
            ' '.join(r['home'].casefold().split()),' '.join(r['away'].casefold().split()))
def score(r):return (int(r['home_goals']),int(r['away_goals']))
def main():
    actual=hashlib.sha256(MASTER.read_bytes()).hexdigest()
    if actual!=EXPECTED:raise RuntimeError('Master changed since approved preflight; abort')
    with MASTER.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;master=list(rd)
    if not fields or not set(FIELDS).issubset(fields):raise RuntimeError('Master schema mismatch')
    if len(master)!=238854:raise RuntimeError('Unexpected master row count')
    with ADD.open(encoding='utf-8-sig',newline='') as f:additions=list(csv.DictReader(f))
    if len(additions)!=760:raise RuntimeError('Expected exactly 760 additions')
    seen={key(r):score(r) for r in master}
    if len(seen)!=len(master):raise RuntimeError('Master contains duplicate fixture keys; abort')
    if Counter((r['league'],r['date'][:4]) for r in additions)!=Counter({('BRA','2025'):380,('JAP','2025'):380}):
        raise RuntimeError('Season counts unexpected')
    for r in additions:
        k=key(r)
        if k in seen:raise RuntimeError(f'Duplicate or conflicting fixture: {k}')
        seen[k]=score(r)
        if any(f not in fields for f in FIELDS):raise RuntimeError('Missing field')
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'historical_matches_candidate_239614.csv'
    with target.open('w',encoding='utf-8',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        wr.writeheader();wr.writerows(master);wr.writerows(additions)
    with target.open(encoding='utf-8',newline='') as f:
        actual_rows=sum(1 for _ in csv.DictReader(f))
    if actual_rows!=239614:raise RuntimeError('Candidate row count mismatch')
    report={'master_sha256':actual,'original_rows':len(master),'added_rows':len(additions),
            'candidate_rows':actual_rows,'candidate_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
            'original_master_modified':False,'status':'candidate_for_review_not_published'}
    (OUT/'promotion_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
