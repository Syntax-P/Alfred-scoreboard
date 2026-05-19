#!/usr/bin/env python3
"""
ScoreBoard — getMLBTeamStats.py
Shows MLB team stats panel: record, home/away splits,
batting, pitching, and next 5 games.
Called by TEXTVIEW-MLB-STATS via Alfred variables.
"""
import os, json, sys, urllib.request, time
from datetime import datetime, date, timedelta

UA    = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
CACHE = os.environ.get("alfred_workflow_cache",
        os.path.join(os.path.expanduser("~"), ".cache", "scoreboard_logos"))
os.makedirs(CACHE, exist_ok=True)
TTL_STATS = 3600        # 1 hour for season stats
TTL_SCHED = 1800        # 30 min for schedule

# ── Alfred env vars set by mlb.py standings items ────────────────────────────
team_id   = os.environ.get("mlbTeamId", "")
team_name = os.environ.get("teamName",  "Unknown Team")
abbrev    = os.environ.get("teamAbbrev","")
div_name  = os.environ.get("divName",   "")
div_rank  = os.environ.get("divRank",   "?")
wins      = os.environ.get("wins",      "0")
losses    = os.environ.get("losses",    "0")
pct_str   = os.environ.get("pct",       "")
gb        = os.environ.get("gb",        "-")
streak    = os.environ.get("streak",    "")

MLB_API   = "https://statsapi.mlb.com/api/v1"
SEASON    = date.today().year

# ── Cache helpers ─────────────────────────────────────────────────────────────
def cache_path(k):
    return os.path.join(CACHE, k.replace("/", "_").replace("?", "_").replace("&", "_") + ".json")

def fetch_json(url, key, ttl):
    cp = cache_path(key)
    try:
        if time.time() - os.path.getmtime(cp) < ttl:
            with open(cp) as f: return json.load(f)
    except: pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        with open(cp, "w") as f: json.dump(data, f)
        return data
    except:
        try:
            with open(cp) as f: return json.load(f)
        except: return None

# ── Fetch helpers ─────────────────────────────────────────────────────────────
def fetch_team_stats(group):
    url = (f"{MLB_API}/teams/{team_id}/stats"
           f"?stats=season&group={group}&season={SEASON}")
    data = fetch_json(url, f"mlb_ts_{team_id}_{group}_{SEASON}", TTL_STATS)
    if not data: return {}
    try:
        return data["stats"][0]["splits"][0]["stat"]
    except: return {}

def fetch_home_away():
    """Return (home_w, home_l, away_w, away_l) by scanning completed schedule."""
    today     = date.today()
    start     = date(SEASON, 3, 1)   # season starts early April, buffer to March
    url = (f"{MLB_API}/schedule?teamId={team_id}"
           f"&startDate={start}&endDate={today}&sportId=1&gameType=R")
    data = fetch_json(url, f"mlb_past_{team_id}_{SEASON}", TTL_STATS)
    if not data: return None

    hw = hl = aw = al = 0
    tid = int(team_id)
    for d_entry in data.get("dates", []):
        for game in d_entry.get("games", []):
            state = game.get("status", {}).get("abstractGameState", "")
            if state != "Final": continue
            t = game.get("teams", {})
            home_team = t.get("home", {})
            away_team = t.get("away", {})
            home_id   = home_team.get("team", {}).get("id")
            away_id   = away_team.get("team", {}).get("id")
            if home_id == tid:
                if home_team.get("isWinner"): hw += 1
                else: hl += 1
            elif away_id == tid:
                if away_team.get("isWinner"): aw += 1
                else: al += 1
    return hw, hl, aw, al

def fetch_next_games():
    """Return list of next 5 upcoming games."""
    today   = date.today()
    end     = today + timedelta(days=60)
    url = (f"{MLB_API}/schedule?teamId={team_id}"
           f"&startDate={today}&endDate={end}&sportId=1&gameType=R")
    data = fetch_json(url, f"mlb_next_{team_id}_{today}", TTL_SCHED)
    if not data: return []

    tid = int(team_id)
    games = []
    for d_entry in data.get("dates", []):
        if len(games) >= 5: break
        for game in d_entry.get("games", []):
            if len(games) >= 5: break
            state = game.get("status", {}).get("abstractGameState", "")
            if state not in ("Preview", "Scheduled"): continue
            t       = game.get("teams", {})
            home    = t.get("home", {})
            away    = t.get("away", {})
            home_id = home.get("team", {}).get("id")
            if home_id == tid:
                ha  = "Home"
                opp = away.get("team", {}).get("name", "?")
            else:
                ha  = "Away"
                opp = home.get("team", {}).get("name", "?")
            venue   = game.get("venue", {}).get("name", "")
            dt_raw  = game.get("gameDate", "")
            try:
                dt = datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
                dt_str = dt.astimezone().strftime("%a %d %b  ·  %-I:%M %p")
            except:
                dt_str = dt_raw[:10]
            games.append({"ha": ha, "opp": opp, "date": dt_str, "venue": venue})
    return games

# ── Formatting helpers ────────────────────────────────────────────────────────
def ordinal(n):
    try:
        n = int(n)
        sfx = ["th","st","nd","rd"]
        s = sfx[n % 10] if n % 10 <= 3 and n not in [11,12,13] else "th"
        return f"{n}{s}"
    except: return str(n)

def build_md(bat, pit, splits, next_games, err=None):
    PAD = 20
    def row(label, val):
        return f"{label}:{' ' * max(1, PAD - len(label))}{val}"

    total = int(wins) + int(losses)
    ppg = round(int(wins) / max(total, 1) * 100)

    lines = [f"# {team_name}"]
    if div_name:
        lines.append(f"*{div_name}  ·  {ordinal(div_rank)} Place*\n")

    # Season record
    lines += ["### Season Record", "```",
        row("Record",    f"W {wins}  L {losses}  ({total} played)"),
        row("Win %",     pct_str or f".{ppg:03d}"),
    ]
    if gb and gb not in ("-", "0", "0.0"):
        lines.append(row("Games Behind", gb))
    if streak:
        lines.append(row("Streak", streak))
    lines.append("```")

    # Home / Away splits
    if splits:
        hw, hl, aw, al = splits
        lines += ["", "### Home vs Away", "```",
            row("Home", f"W {hw}  L {hl}  ({hw + hl} games)"),
            row("Away", f"W {aw}  L {al}  ({aw + al} games)"),
        "```"]

    # Batting
    if bat:
        avg  = bat.get("avg",          "—")
        obp  = bat.get("obp",          "—")
        slg  = bat.get("slg",          "—")
        ops  = bat.get("ops",          "—")
        hrs  = bat.get("homeRuns",     "—")
        runs = bat.get("runs",         "—")
        hits = bat.get("hits",         "—")
        so   = bat.get("strikeOuts",   "—")
        bb   = bat.get("baseOnBalls",  "—")
        gpb  = max(total, 1)
        rpg  = round(int(runs) / gpb, 2) if str(runs).isdigit() else "—"
        lines += ["", "### Team Batting", "```",
            row("AVG / OBP / SLG", f"{avg}  /  {obp}  /  {slg}"),
            row("OPS",             str(ops)),
            row("Home Runs",       str(hrs)),
            row("Runs",            f"{runs}  ({rpg} per game)"),
            row("Hits",            str(hits)),
            row("K / BB",          f"{so}  /  {bb}"),
        "```"]

    # Pitching
    if pit:
        era  = pit.get("era",        "—")
        whip = pit.get("whip",       "—")
        kk   = pit.get("strikeOuts", "—")
        bb   = pit.get("baseOnBalls","—")
        ip   = pit.get("inningsPitched", "—")
        lines += ["", "### Team Pitching", "```",
            row("ERA",             str(era)),
            row("WHIP",            str(whip)),
            row("Innings Pitched", str(ip)),
            row("Strikeouts",      str(kk)),
            row("Walks",           str(bb)),
        "```"]

    if err:
        lines += ["", f"*⚠️  {err}*"]

    # Next games
    if next_games:
        lines += ["", "### Next 5 Games"]
        for g in next_games:
            venue_str = f"  ·  {g['venue']}" if g.get("venue") else ""
            lines.append(f"📅  {g['ha']}  vs  {g['opp']}")
            lines.append(f"     {g['date']}{venue_str}")

    return "\n".join(lines)

def main():
    bat = pit = splits = None
    next_games = []
    err = None

    if not team_id:
        err = "No team ID — select a team from mlbstandings"
    else:
        try:
            bat        = fetch_team_stats("hitting")
            pit        = fetch_team_stats("pitching")
            splits     = fetch_home_away()
            next_games = fetch_next_games()
        except Exception as ex:
            err = str(ex)

    try:
        md = build_md(bat, pit, splits, next_games, err)
    except Exception as ex:
        md = f"# {team_name}\n\nError building stats: {ex}"

    sys.stdout.write(json.dumps({
        "response": md,
        "footer":   "⌘↩  Open team page on ESPN"
    }))

main()
