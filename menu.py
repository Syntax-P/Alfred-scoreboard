#!/usr/bin/env python3
"""
ScoreBoard — menu.py
Branded entry point. Shows all 5 leagues as selectable options.
Triggered by hotkey or `scoreboard` keyword.
"""
import sys, json, os

LEAGUES = [
    ("ENG.1", "Premier League",  "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "leagues/epl.svg",        "epl",        "epltable"),
    ("GER.1", "Bundesliga",      "🇩🇪", "leagues/bundesliga.svg", "bundesliga", "bundesligatable"),
    ("ESP.1", "La Liga",         "🇪🇸", "leagues/laliga.svg",     "laliga",     "laligatable"),
    ("ITA.1", "Serie A",         "🇮🇹", "leagues/seriea.svg",     "seriea",     "serieastable"),
    ("FRA.1",   "Ligue 1",          "🇫🇷", "leagues/ligue1.svg", "ligue1", "ligue1table"),
    ("UEFA.CL", "Champions League", "🏆", "leagues/ucl.svg",   "ucl",    "ucltable"),
    ("UEFA.EL", "Europa League",    "🟠", "leagues/uel.svg",   "uel",    "ueltable"),
]

q = (sys.argv[1].strip().lower() if len(sys.argv) > 1 else "")

items = []

# Header items — show all scores or all tables
items.append({
    "title":    "⚽  All Scores Today",
    "subtitle": "View live scores across all 5 leagues",
    "arg":      os.environ.get("keyword_scores","scores"),
    "valid":    True,
    "icon":     {"path": "leagues/all.svg"},
    "mods": {
        "cmd": {"subtitle": "Open ESPN Soccer", "arg": "https://www.espn.com/soccer/"}
    }
})

# Per-league entries
for slug, name, flag, icon, score_kw, table_kw in LEAGUES:
    if q and q not in name.lower() and q not in score_kw:
        continue
    items.append({
        "title":    f"{flag}  {name}",
        "subtitle": f"↩ scores  ·  ⌘↩ table",
        "arg":      score_kw,
        "valid":    True,
        "icon":     {"path": icon},
        "mods": {
            "cmd": {
                "subtitle": f"Open {name} table",
                "arg":      table_kw,
            }
        }
    })

# Reload option at bottom
items.append({
    "title":    "🔄  Refresh All Data",
    "subtitle": "Clear cache and reload scores, standings and fixtures",
    "arg":      "scores:reload",
    "valid":    True,
    "icon":     {"path": "leagues/all.svg"},
})

if not items:
    items = [{"title": "No leagues matched", "valid": False}]

print(json.dumps({"items": items}))
