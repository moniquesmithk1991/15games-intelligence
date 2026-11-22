#!/usr/bin/env python3
"""Fetch ESPN public scoreboards for Brazil and Argentina; NOT an official federation feed."""
import datetime,json,urllib.request,pathlib
OUT=pathlib.Path("data/south_america_matches.json")
LEAGUES={"BRA1":"bra.1","ARG1":"arg.1"}
today=datetime.datetime.now(datetime.timezone.utc).date()
records=[];errors=[]
for league,code in LEAGUES.items():
  for offset in range(-14,8):
    date=today+datetime.timedelta(days=offset)
    url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={date:%Y%m%d}&limit=100"
    try:
      req=urllib.request.Request(url,headers={"User-Agent":"15GAMES-Research/1.0"})
      with urllib.request.urlopen(req,timeout=20) as response: data=json.load(response)
      for e in data.get("events",[]):
        comp=(e.get("competitions") or [{}])[0]; teams=comp.get("competitors") or []
        home=next((t for t in teams if t.get("homeAway")=="home"),None)
        away=next((t for t in teams if t.get("homeAway")=="away"),None)
        if not home or not away:continue
        state=e.get("status",{}).get("type",{}).get("state","")
        score=lambda t: int(t["score"]) if str(t.get("score","")).isdigit() else None
        records.append({"id":str(e.get("id")),"league":league,"date":e.get("date"),"home":home.get("team",{}).get("displayName"),"away":away.get("team",{}).get("displayName"),"home_goals":score(home) if state=="post" else None,"away_goals":score(away) if state=="post" else None,"status":state,"source":"ESPN public scoreboard","source_url":url})
    except Exception as exc:errors.append({"league":league,"date":str(date),"error":str(exc)[:120]})
unique={r["league"]+":"+r["id"]:r for r in records}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps({"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"source_type":"third-party ESPN, not official AFA/CBF","matches":sorted(unique.values(),key=lambda x:x["date"] or ""),"errors":errors},ensure_ascii=False,indent=2)+"\n")
print(f"saved {len(unique)} matches; {len(errors)} request errors")
