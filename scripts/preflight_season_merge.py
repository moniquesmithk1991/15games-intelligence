#!/usr/bin/env python3
"""Build a reviewed, non-destructive master candidate from two complete seasons.

Only creates outputs under data/merge_review/. Does not edit master or staging.
"""
import csv, json, hashlib
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
MASTER=ROOT/'historical_matches.csv'
OUT=ROOT/'data/merge_review'
INPUTS=[
 ROOT/'data/staging/brazil_serie_a_2025_complete_380_review.csv',
 ROOT/'data/japan_official_review/japan_j1_2025_complete_380_review.csv',
]
REQUIRED=('date','league','home','away','home_goals','away_goals')
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not set(REQUIRED).issubset(reader.fieldnames or []):raise ValueError(f'Invalid columns: {path}')
        return reader.fieldnames,list(reader)
def key(r):
    return (r['date'].strip(),r['league'].strip().upper(),
            ' '.join(r['home'].casefold().split()),' '.join(r['away'].casefold().split()))
def score(r):return (int(r['home_goals']),int(r['away_goals']))
def save(name,fields,rows):
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    master_fields,master_rows=read(MASTER)
    original_hash=hashlib.sha256(MASTER.read_bytes()).hexdigest()
    if len(master_rows)<200000:raise RuntimeError('Unexpectedly small master; stop')
    original={}
    for r in master_rows:
        k=key(r)
        if k in original and score(original[k])!=score(r):raise RuntimeError(f'Existing master conflict: {k}')
        original[k]=r
    added=[];duplicates=[];conflicts=[];staged_seen=set()
    for p in INPUTS:
        fields,rows=read(p)
        if len(rows)!=380:raise RuntimeError(f'{p.name}: expected 380, got {len(rows)}')
        for r in rows:
            k=key(r)
            if k in staged_seen:raise RuntimeError(f'Duplicate staged fixture: {k}')
            staged_seen.add(k)
            if k in original:
                (duplicates if score(original[k])==score(r) else conflicts).append({'source':p.name,**r})
            else:added.append({'source':p.name,**r})
    save('candidate_additions.csv',['source',*REQUIRED,'source_url'],added)
    save('already_in_master.csv',['source',*REQUIRED,'source_url'],duplicates)
    save('score_conflicts.csv',['source',*REQUIRED,'source_url'],conflicts)
    summary={'master_rows':len(master_rows),'master_sha256':original_hash,
             'season_inputs':{p.name:380 for p in INPUTS},
             'new_candidates':len(added),'already_in_master':len(duplicates),
             'score_conflicts':len(conflicts),
             'master_modified':False,'status':'review_required_no_auto_merge'}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    if conflicts:raise RuntimeError('Score conflicts detected: review before promotion')
if __name__=='__main__':main()
