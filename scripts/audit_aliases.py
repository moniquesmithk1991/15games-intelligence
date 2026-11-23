#!/usr/bin/env python3
"""Read-only second-pass audit: identify potential aliases for staged fixtures.

Never merges or changes master data. Review candidate pairs manually.
"""
import csv, json, re, unicodedata
from collections import defaultdict, Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MASTER=ROOT/'historical_matches.csv'
STAGED=ROOT/'data/audit/new_candidates.csv'
OUT=ROOT/'data/alias_audit'
COMMON={'fc','cf','sc','ac','ca','ec','cr','fbpa','fbc','club','clube','football','futebol','soccer','de','da','do','the','se','ss','afc','fk','cd'}
def canon(s):
    s=unicodedata.normalize('NFKD',str(s or '')).encode('ascii','ignore').decode().lower()
    s=re.sub(r'[^a-z0-9]+',' ',s)
    words=[w for w in s.split() if w not in COMMON]
    return ' '.join(words)
def key(row):
    return (row.get('date','').strip()[:10],row.get('league','').strip().upper())
def score(row):
    try:return (int(row['home_goals']),int(row['away_goals']))
    except (KeyError,ValueError):return None
def similarity(a,b):
    a,b=canon(a),canon(b)
    if not a or not b:return 0
    if a==b:return 1
    return SequenceMatcher(None,a,b).ratio()
def load(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(name,rows,fields):
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def main():
    if not STAGED.exists():raise SystemExit('Run scripts/audit_staging.py first')
    master=defaultdict(list)
    for r in load(MASTER):master[key(r)].append(r)
    likely=[];review=[];unmatched=[]
    for r in load(STAGED):
        candidates=[]
        for m in master.get(key(r),[]):
            h=similarity(r.get('home'),m.get('home'))
            a=similarity(r.get('away'),m.get('away'))
            if h>=.60 and a>=.60:
                candidates.append((min(h,a),(h+a)/2,m))
        candidates.sort(key=lambda x:(x[0],x[1]),reverse=True)
        if candidates:
            minimum,average,m=candidates[0]
            item={**r,'master_home':m.get('home',''),'master_away':m.get('away',''),
                  'master_home_goals':m.get('home_goals',''),'master_away_goals':m.get('away_goals',''),
                  'home_similarity':round(similarity(r.get('home'),m.get('home')),3),
                  'away_similarity':round(similarity(r.get('away'),m.get('away')),3),
                  'score_agrees':str(score(r)==score(m))}
            if minimum>=.85 and score(r)==score(m):
                likely.append(item)
            else:review.append(item)
        else:unmatched.append(r)
    fields=['file','line','date','league','home','away','home_goals','away_goals','source_url',
            'master_home','master_away','master_home_goals','master_away_goals',
            'home_similarity','away_similarity','score_agrees']
    write('likely_existing.csv',likely,fields)
    write('manual_review.csv',review,fields)
    write('no_alias_candidate.csv',unmatched,fields)
    summary={'staged_candidates':len(likely)+len(review)+len(unmatched),
             'likely_existing':len(likely),'manual_review':len(review),
             'no_alias_candidate':len(unmatched),
             'note':'Fuzzy matching is suggestive, not proof. No files merged. Missing alias candidate does not prove fixture is new.'}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
