#!/usr/bin/env python3
"""Inspect upstream OpenFootball fixture/score coverage; never modify master."""
import csv,json,urllib.request,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/source_coverage_review'
SOURCES={
 'argentina_2025':('https://raw.githubusercontent.com/openfootball/football.json/master/2025/ar.1.json','data/staging/argentina_primera_2025_source_ft.csv'),
 'brazil_2026':('https://raw.githubusercontent.com/openfootball/football.json/master/2026/br.1.json','data/staging/brazil_serie_a_2026_verified_ft.csv')
}
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 result={}
 for name,(url,staged) in SOURCES.items():
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'15GAMES-audit'}),timeout=40) as response:
   data=json.load(response)
  matches=data.get('matches',[])
  if not isinstance(matches,list):raise ValueError(f'{name}: source has no matches list')
  scored=collections.Counter();no_score=0;zero_zero=0;unknown=0
  for m in matches:
   s=m.get('score')
   if not isinstance(s,dict):no_score+=1;continue
   ft=s.get('ft')
   if isinstance(ft,list) and len(ft)==2 and all(isinstance(x,int) and x>=0 for x in ft):
    scored['has_ft']+=1
    if ft==[0,0]:zero_zero+=1
   else:no_score+=1
  with (ROOT/staged).open(encoding='utf-8-sig',newline='') as f:
   rows=list(csv.DictReader(f))
  result[name]={'source_url':url,'upstream_fixture_count':len(matches),'upstream_ft_score_entries':scored['has_ft'],
    'upstream_zero_zero_entries_require_independent_confirmation':zero_zero,
    'upstream_missing_ft':no_score,'staged_results':len(rows),
    'staged_first_date':min(r['date'] for r in rows),'staged_last_date':max(r['date'] for r in rows),
    'note':'Source coverage inventory only; 0-0 entries may represent placeholders. Do not auto-merge.'}
 (OUT/'source_coverage.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
