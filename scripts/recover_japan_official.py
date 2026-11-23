#!/usr/bin/env python3
"""Recover Japan J1 2025 FT results from the official J.League results table.

Read-only: outputs review CSVs; does not alter staging source or master database.
"""
import csv, io, json, re, urllib.request
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/'data/staging/japan_j1_2025_remaining_140_queue.csv'
OUT=ROOT/'data/japan_official_review'
URL='https://data.j-league.or.jp/SFMS01/search?competition_frame_ids=1&competition_ids=651&competition_years=2025'
CLUBS={
'FC東京':'FC Tokyo','京都':'Kyoto Sanga FC','名古屋':'Nagoya Grampus','岡山':'Fagiano Okayama',
'川崎Ｆ':'Kawasaki Frontale','広島':'Sanfrecce Hiroshima','新潟':'Albirex Niigata',
'東京Ｖ':'Tokyo Verdy','柏':'Kashiwa Reysol','横浜FC':'Yokohama FC','横浜FM':'Yokohama F. Marinos',
'浦和':'Urawa Red Diamonds','清水':'Shimizu S-Pulse','湘南':'Shonan Bellmare',
'町田':'FC Machida Zelvia','神戸':'Vissel Kobe','福岡':'Avispa Fukuoka',
'鹿島':'Kashima Antlers','Ｃ大阪':'Cerezo Osaka','Ｇ大阪':'Gamba Osaka'
}
def norm(s):
    return re.sub(r'\s+','',s).strip()
def save(path, rows, fields):
    with (OUT/path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        w.writeheader();w.writerows(rows)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with QUEUE.open(encoding='utf-8-sig',newline='') as f: queue=list(csv.DictReader(f))
    req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 (15GAMES historical verification; research)'})
    with urllib.request.urlopen(req,timeout=45) as res: html=res.read().decode('utf-8','replace')
    soup=BeautifulSoup(html,'html.parser')
    official={}
    by_pair={}
    unknown=[]
    for tr in soup.select('tr'):
        cells=[x.get_text(' ',strip=True) for x in tr.find_all(['td','th'],recursive=False)]
        if len(cells)<8:continue
        # Official table: season, competition, round, date, KO, home, score, away, ...
        if cells[0]!='2025' or 'Ｊ１' not in cells[1]:continue
        dm=re.search(r'(\d{2})/(\d{2})/(\d{2})',cells[3])
        sm=re.fullmatch(r'(\d+)\s*[-–]\s*(\d+)',cells[6])
        home=CLUBS.get(norm(cells[5]))
        away=CLUBS.get(norm(cells[7]))
        if not (dm and sm and home and away):
            unknown.append({'date':cells[3],'home':cells[5],'score':cells[6],'away':cells[7]})
            continue
        key=(f'20{dm[1]}-{dm[2]}-{dm[3]}',home,away)
        score=(int(sm[1]),int(sm[2]))
        if key in official and official[key]!=score:raise RuntimeError(f'Conflicting official scores: {key}')
        official[key]=score
        by_pair.setdefault((home,away),[]).append((key[0],score))
    if len(official)<300:
        raise RuntimeError(f'Official page parsed only {len(official)} fixtures; expected >=300. Refusing incomplete recovery.')
    matched=[];remaining=[];date_mismatches=[]
    for r in queue:
        key=(r['date'],r['home'],r['away'])
        score=official.get(key)
        if score is None:
            remaining.append(r)
            candidates=by_pair.get((r['home'],r['away']),[])
            if len(candidates)==1:
                official_date,official_score=candidates[0]
                date_mismatches.append({'source_date':r['date'],'official_date':official_date,
                    'league':'JAP','home':r['home'],'away':r['away'],
                    'home_goals':official_score[0],'away_goals':official_score[1],
                    'source_url':URL,'status':'date_mismatch_review'})
        else:matched.append({'date':r['date'],'league':'JAP','home':r['home'],'away':r['away'],
                            'home_goals':score[0],'away_goals':score[1],'source_url':URL})
    save('recovered_official.csv',matched,['date','league','home','away','home_goals','away_goals','source_url'])
    save('still_unmatched.csv',remaining,list(queue[0]) if queue else ['date','league','home','away'])
    save('date_mismatch_review.csv',date_mismatches,['source_date','official_date','league','home','away','home_goals','away_goals','source_url','status'])
    save('unparsed_official_rows.csv',unknown,['date','home','score','away'])
    summary={'official_fixtures_parsed':len(official),'queued':len(queue),
             'recovered':len(matched),'remaining':len(remaining),
             'date_mismatch_candidates':len(date_mismatches),
             'unparsed_official_rows':len(unknown),'source':URL,
             'status':'review_only_no_master_merge'}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))
    if len(queue)!=140:raise RuntimeError(f'Expected 140 queued rows; got {len(queue)}')
    if len(official)!=380:raise RuntimeError(f'Expected 380 official fixtures; got {len(official)}')
    if len(matched)!=119 or len(date_mismatches)!=21:
        raise RuntimeError('Unexpected reconciliation counts; stop for manual review')
    # Compare all 380 official fixtures to the previously staged 127 + 113.
    staged_files=[
        ROOT/'data/staging/japan_j1_2025_source_ft.csv',
        ROOT/'data/staging/japan_j1_2025_recovered_113_ft.csv'
    ]
    staged={}
    for p in staged_files:
        with p.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                pair=(row['home'],row['away'])
                if pair in staged:raise RuntimeError(f'Duplicate staged fixture: {pair}')
                staged[pair]=row
    if len(staged)!=240:raise RuntimeError(f'Expected 240 staged results; got {len(staged)}')
    official_pairs={}
    for (date,home,away),sc in official.items():
        pair=(home,away)
        if pair in official_pairs:raise RuntimeError(f'Duplicate official fixture pair: {pair}')
        official_pairs[pair]=(date,sc)
    if len(official_pairs)!=380:raise RuntimeError('Official fixture pairs not unique')
    conflicts=[]
    for pair,row in staged.items():
        entry=official_pairs.get(pair)
        if entry is None:
            conflicts.append({'home':pair[0],'away':pair[1],'issue':'not_in_official'})
        elif (int(row['home_goals']),int(row['away_goals']))!=entry[1]:
            conflicts.append({'home':pair[0],'away':pair[1],'issue':'score_conflict'})
    save('existing_staged_conflicts.csv',conflicts,['home','away','issue'])
    if conflicts:
        raise RuntimeError(f'{len(conflicts)} staged score/pair conflicts: review before assembly')
    complete=[]
    for (date,home,away),sc in sorted(official.items()):
        complete.append({'date':date,'league':'JAP','home':home,'away':away,
                         'home_goals':sc[0],'away_goals':sc[1],'source_url':URL})
    save('japan_j1_2025_complete_380_review.csv',complete,
         ['date','league','home','away','home_goals','away_goals','source_url'])
    print('Complete official 380-match review file assembled; master unchanged.')
if __name__=='__main__':main()
