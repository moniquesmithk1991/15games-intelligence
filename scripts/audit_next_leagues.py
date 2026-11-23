#!/usr/bin/env python3
"""Read-only inventory of Argentina 2025 and Brazil 2026 staged FT results vs master V2."""
import csv,datetime as dt,hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MASTER=ROOT/'historical_matches_v2_239614.csv'
STAGING=ROOT/'data/staging'
OUT=ROOT/'data/next_leagues_review'
REQUIRED={'date','league','home','away','home_goals','away_goals'}
def load(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not REQUIRED.issubset(reader.fieldnames or []):raise ValueError(f'Invalid schema: {path}')
        return list(reader)
def key(r):
    return (r['date'].strip()[:10],r['league'].strip().upper(),' '.join(r['home'].casefold().split()),' '.join(r['away'].casefold().split()))
def score(r):
    a,b=r['home_goals'].strip(),r['away_goals'].strip()
    if not (a.isdecimal() and b.isdecimal() and int(a)<=30 and int(b)<=30):raise ValueError('Invalid goals')
    return (int(a),int(b))
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base=load(MASTER)
    if len(base)!=239614:raise RuntimeError('Master V2 count changed; abort')
    master={key(r):score(r) for r in base}
    if len(master)!=len(base):raise RuntimeError('Duplicate keys in V2')
    paths=sorted(p for p in STAGING.glob('*.csv') if (('argentina' in p.name.lower() and '2025' in p.name.lower()) or ('brazil' in p.name.lower() and '2026' in p.name.lower())) and not any(w in p.name.lower() for w in ('queue','missing','review','recovered','zero_zero')))
    if not paths:raise RuntimeError('No Argentina 2025 or Brazil 2026 staging files found')
    candidates=[];already=[];conflicts=[];invalid=[];seen={};files={}
    for p in paths:
        rows=load(p);files[p.name]=len(rows)
        for line,r in enumerate(rows,2):
            info={'source_file':p.name,'source_line':line,**r}
            try:
                k=key(r);s=score(r)
                dt.date.fromisoformat(k[0])
                if not k[1] or not k[2] or not k[3] or k[2]==k[3]:raise ValueError('Invalid teams or league')
                expected=('ARG','2025') if 'argentina' in p.name.lower() else ('BRA','2026')
                if (k[1],k[0][:4])!=expected:raise ValueError(f'Unexpected league/year: {k[1]}, {k[0]}')
            except (ValueError,KeyError) as e:
                invalid.append({**info,'reason':str(e)});continue
            if k in seen:
                (conflicts if seen[k]!=s else already).append({**info,'reason':'staging_duplicate_or_conflict'});continue
            seen[k]=s
            if k in master:
                (already if master[k]==s else conflicts).append({**info,'reason':'already_in_v2' if master[k]==s else 'score_conflict_with_v2'})
            else:candidates.append(info)
    cols=['source_file','source_line','date','league','home','away','home_goals','away_goals','source_url','reason']
    for name,rows in [('candidates.csv',candidates),('already_in_v2.csv',already),('conflicts.csv',conflicts),('invalid.csv',invalid)]:
        with (OUT/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(rows)
    summary={'master_v2_rows':len(base),'master_v2_sha256':hashlib.sha256(MASTER.read_bytes()).hexdigest(),'staging_files':files,'candidate_rows':len(candidates),'already_or_duplicate_rows':len(already),'conflicts':len(conflicts),'invalid':len(invalid),'warning':'Read-only staging audit. Fixture identity and aliases require independent verification; do not auto-merge.'}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
