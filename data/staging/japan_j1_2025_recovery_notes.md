# Japan J1 2025 — score recovery queue

- Expected season fixtures: 380
- Previously staged full-time results: 127
- Fixtures requiring independent score verification: 253
- No score in OpenFootball source: 244
- Ambiguous bare 0–0 array: 9
- Source: https://raw.githubusercontent.com/openfootball/football.json/master/2025/jp.1.json

This file is an **inventory**, not a completed-results CSV. It deliberately omits home_goals and away_goals to prevent unknown scores from being imported as zeroes.

Next: verify the 253 fixture results against an independent historical source, record source URLs, then stage only confirmed full-time scores. Never merge this inventory into historical_matches.csv.
