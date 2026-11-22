#!/usr/bin/env python3
"""Historical backfill from ESPN public scoreboard. Third-party, not official federation data.
Uses daily scoreboard queries, preserving previous results and refusing incomplete-score finals.
"""
import datetime,json,pathlib,urllib.request,os,concurrent.futures
OUT=pathlib.Path("data/south_america_matches.json")
LEAGUES={"BRA1":"bra.1","BRA2":"bra.2","ARG1":"arg.1","ARG2":"arg.2"}
START_YEAR=int(os.environ.get("START_YEAR","2026"))
END_YEAR=int(os.environ.get("END_YEAR",str(START_YEAR)))
if START_YEAR<2020 or END_YEAR>2030 or END_YEAR<START_YEAR:raise ValueError("Invalid year range")
old={}
if OUT.exists():
  try:
    old_data=json.loads(OUT.read_text())
    old={x["league"]+":"+str(x["id"]):x for x in old_data.get("matches",[]) if x.get("league") and x.get("id")}
  except (ValueError,KeyError,TypeError):pass
errors=[];found=0
tasks=[]
today=datetime.datetime.now(datetime.timezone.utc).date()
for league,code in LEAGUES.items():
  for year in range(START_YEAR,END_YEAR+1):
    day=datetime.date(year,1,1)
    while day<=min(today,datetime.date(year,12,31)):
      tasks.append((league,code,day))
      day+=datetime.timedelta(days=1)
def fetch_day(task):
  league,code,day=task
  url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={day:%Y%m%d}&limit=100"
  try:
    req=urllib.request.Request(url,headers={"User-Agent":"15GAMES-Research/1.0"})
    with urllib.request.urlopen(req,timeout=20) as response:data=json.load(response)
    return league,url,data,None
  except Exception as exc:
    return league,url,None,str(exc)[:160]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  for league,url,data,error in pool.map(fetch_day,tasks):
    if error:
      errors.append({"league":league,"url":url,"error":error})
      continue
    for e in data.get("events",[]):
      comp=(e.get("competitions") or [{}])[0]
      teams=comp.get("competitors") or []
      h=next((t for t in teams if t.get("homeAway")=="home"),None)
      a=next((t for t in teams if t.get("homeAway")=="away"),None)
      if not h or not a:continue
      state=e.get("status",{}).get("type",{}).get("state","")
      score=lambda t:int(t["score"]) if str(t.get("score","")).isdigit() else None
      hg=score(h) if state=="post" else None
      ag=score(a) if state=="post" else None
      if state=="post" and (hg is None or ag is None):continue
      item={"id":str(e.get("id")),"league":league,"date":e.get("date"),"home":h.get("team",{}).get("displayName"),"away":a.get("team",{}).get("displayName"),"home_team_id":str(h.get("team",{}).get("id","")),"away_team_id":str(a.get("team",{}).get("id","")),"home_goals":hg,"away_goals":ag,"status":state,"source":"ESPN public scoreboard","source_url":url}
      key=league+":"+item["id"]
      if key in old and old[key].get("status")=="post" and state!="post":continue
      old[key]=item
      found+=1
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps({"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"source_type":"third-party ESPN, not official AFA/CBF","matches":sorted(old.values(),key=lambda x:x.get("date") or ""),"errors":errors,"backfill":{"years":[START_YEAR,END_YEAR],"observations":found}},ensure_ascii=False,indent=2)+"\n")
print(f"Backfill observations: {found}; cumulative matches: {len(old)}; request errors: {len(errors)}")
