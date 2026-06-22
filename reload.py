#!/usr/bin/env python3
"""
ScoreBoard — reload.py
Clears all cached data and triggers a fresh fetch.
Called by the `scores:reload` keyword.
"""
import os, json, glob, sys

CACHE = os.environ.get("alfred_workflow_cache",
        os.path.join(os.path.expanduser("~"), ".cache", "scoreboard_logos"))

removed = 0
# Clear JSON caches (scores, standings, schedule, fixtures)
for pattern in ["scores_*.json", "standings_*.json", "sched_*.json",
                "sb_*.json", "sb_fix_*.json", "teamstats_*.json"]:
    for f in glob.glob(os.path.join(CACHE, pattern)):
        try:
            os.remove(f)
            removed += 1
        except: pass

# Output in Script Filter format with variables for notification
print(json.dumps({
    "variables": {
        "notification_title": "ScoreBoard Refreshed",
        "notification_text":  "Cache cleared — scores will reload fresh"
    },
    "items": [{
        "title":    "Cache Cleared",
        "subtitle": f"Removed {removed} cached files — scores will reload fresh",
        "valid":    True,
        "arg":      f"Cleared {removed} cached files",
        "icon":     {"path": "icon.png"}
    }]
}))
