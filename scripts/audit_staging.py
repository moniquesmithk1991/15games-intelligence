#!/usr/bin/env python3
"""Compare 15GAMES staged results with the master historical CSV.

Read-only: never modifies the master or staged inputs.
Run from repository root: python3 scripts/audit_staging.py
"""
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "historical_matches.csv"
STAGING = ROOT / "data" / "staging"
OUT = ROOT / "data" / "audit"
REQUIRED = ("date", "league", "home", "away", "home_goals", "away_goals")


def normalized(name):
    return " ".join(str(name or "").strip().casefold().split())


def parse_date(raw):
    value = str(raw or "").strip()[:10]
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def parse_goals(raw):
    s = str(raw or "").strip()
    if not s.isdecimal():
        return None
    n = int(s)
    return n if 0 <= n <= 30 else None


def read_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = [c for c in REQUIRED if c not in fields]
        if missing:
            raise ValueError(f"{path}: missing columns {', '.join(missing)}")
        return list(reader)


def validate(row):
    date = parse_date(row.get("date"))
    league = normalized(row.get("league")).upper()
    home = normalized(row.get("home"))
    away = normalized(row.get("away"))
    hg = parse_goals(row.get("home_goals"))
    ag = parse_goals(row.get("away_goals"))
    problems = []
    if date is None: problems.append("invalid_date")
    if not league: problems.append("missing_league")
    if not home or not away or home == away: problems.append("invalid_teams")
    if hg is None or ag is None: problems.append("invalid_score")
    if problems: return None, None, problems
    return (date, league, home, away), (hg, ag), []


def save_csv(name, rows, columns):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not MASTER.is_file(): raise SystemExit(f"Missing master: {MASTER}")
    paths = sorted(STAGING.glob("*.csv"))
    if not paths: raise SystemExit("No staging CSV files found")
    master = {}
    master_invalid = 0
    for row in read_rows(MASTER):
        key, score, problems = validate(row)
        if problems:
            master_invalid += 1
            continue
        if key in master and master[key] != score:
            print("WARNING: master has conflicting scores for", key)
        master.setdefault(key, score)
    new, dup, conflicts, invalid, alias_review = [], [], [], [], []
    seen = {}
    counts = Counter()
    for path in paths:
        for line_no, row in enumerate(read_rows(path), 2):
            base = {"file": path.name, "line": line_no, **row}
            key, score, problems = validate(row)
            counts["staged"] += 1
            if problems:
                invalid.append({**base, "issue": ";".join(problems)})
                counts["invalid"] += 1
                continue
            if key in seen:
                if seen[key] != score:
                    conflicts.append({**base, "issue":"staging_score_conflict", "master_score":str(seen[key])})
                    counts["conflicts"] += 1
                else:
                    dup.append({**base,"issue":"duplicate_within_staging"})
                    counts["duplicates"] += 1
                continue
            seen[key] = score
            if key in master:
                if master[key] == score:
                    dup.append({**base,"issue":"already_in_master"})
                    counts["duplicates"] += 1
                else:
                    conflicts.append({**base,"issue":"score_differs_from_master","master_score":str(master[key])})
                    counts["conflicts"] += 1
            else:
                new.append(base)
                counts["new_candidates"] += 1
    # Name differences are not auto-resolved. These candidates must be reviewed
    # against aliases before any merge is allowed.
    csvcols = ("file","line","date","league","home","away","home_goals","away_goals","source_url","issue","master_score")
    save_csv("new_candidates.csv", new, csvcols)
    save_csv("duplicates.csv", dup, csvcols)
    save_csv("score_conflicts.csv", conflicts, csvcols)
    save_csv("invalid.csv", invalid, csvcols)
    summary = {"master_valid_unique":len(master),"master_invalid":master_invalid,"staging_files":[p.name for p in paths],**counts,
               "warning":"New candidates are NOT verified as absent unless team aliases are reconciled. Never auto-merge."}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))
    print("Wrote read-only review outputs to data/audit/")


if __name__ == "__main__":
    main()
