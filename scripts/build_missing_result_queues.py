#!/usr/bin/env python3
"""Create read-only fixture queues for independently verifying missing scores."""
import csv,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/missing_results_review'
SOURCES={
 'argentina_2025':'https://raw.githubusercontent.com/openfootball/football.json/master/2025/ar.1.json',
 'brazil_2026':'https://raw.githubusercontent.com/openfootball/football.json/master/2026/br.1.json'
}
def name(x):
 if isinstance(x,str):return x
 if isinstance(x,dict):return str(x.get('name') or x.get('team') or x.get('title') or '')
 return str(x or '')
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 report={}
 for label,url in SOURCES.items():
  req=urllib.request.Request(url,headers={'User-Agent':'15GAMES-source-audit'})
  with urllib.request.urlopen(req,timeout=45) as resp: data=json.load(resp)
  rows=[];valid=0
  for m in data.get('matches',[]):
   score=m.get('score')
   ft=score.get('ft') if isinstance(score,dict) else None
   if isinstance(ft,list) and len(ft)==2 and all(type(v)==int and v>=0 for v in ft):
    valid+=1;continue
   rows.append({'date':str(m.get('date') or ''),'home':name(m.get('team1') or m.get('home') or m.get('home_team')),
    'away':name(m.get('team2') or m.get('away') or m.get('away_team')),
    'source_url':url,'status':'missing_score_verify_independently'})
  with (OUT/(label+'_missing_queue.csv')).open('w',newline='',encoding='utf-8') as f:
   w=csv.DictWriter(f,fieldnames=['date','home','away','source_url','status']);w.writeheader();w.writerows(rows)
  report[label]={'source_fixtures':len(data.get('matches',[])),'scored':valid,'missing':len(rows),
    'missing_dates':sorted(set(x['date'] for x in rows)),
    'blank_team_names':sum(not x['home'] or not x['away'] for x in rows)}
 (OUT/'queue_summary.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:{q:v for q,v in d.items() if q!='missing_dates'} for k,d in report.items()},indent=2))
if __name__=='__main__':main()
