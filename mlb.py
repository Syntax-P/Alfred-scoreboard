#!/usr/bin/env python3
"""
ScoreBoard — mlb.py
Fetches MLB scores and standings from ESPN.
Usage:
  mlb.py           → today's scores
  mlb.py standings → AL/NL standings
"""
import sys, json, os, urllib.request, time
from datetime import datetime

UA    = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
CACHE = os.environ.get("alfred_workflow_cache",
        os.path.join(os.path.expanduser("~"), ".cache", "scoreboard_logos"))
os.makedirs(CACHE, exist_ok=True)
SCORE_TTL    = int(os.environ.get("score_refresh","60"))
STANDING_TTL = 4 * 3600

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb"

STATE_ICON  = {"pre":"🕐","in":"🔴","post":"✅"}
STATE_ORDER = {"in":0,"pre":1,"post":2}

def cache_path(k): return os.path.join(CACHE, k.replace("/","_")+".json")

def load_cache(k, ttl=None):
    try:
        p=cache_path(k)
        if ttl is None or time.time()-os.path.getmtime(p)<ttl:
            with open(p) as f: return json.load(f)
    except: pass

def save_cache(k, data):
    try:
        with open(cache_path(k),"w") as f: json.dump(data,f)
    except: pass

def fetch_json(url, key, ttl):
    c=load_cache(key,ttl)
    if c is not None: return c, False
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=8) as r: data=json.loads(r.read())
        save_cache(key,data); return data, False
    except Exception as ex:
        stale=load_cache(key)
        if stale is not None: return stale, True
        raise ex

def download_logo(url, tid):
    if not url or not tid: return None
    p=os.path.join(CACHE,f"{tid}.png")
    if not os.path.exists(p):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA})
            with urllib.request.urlopen(req,timeout=5) as r:
                with open(p,"wb") as f: f.write(r.read())
        except: return None
    return p

MLB_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leagues", "mlb.svg")

def home_icon(team):
    logo = team.get("logo","")
    tid  = team.get("id","")
    return download_logo(logo, tid) or MLB_ICON

def local_time(s):
    try:
        dt=datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.astimezone().strftime("%-I:%M %p")
    except: return s

def game_link(event):
    for lk in event.get("links",[]):
        if not lk.get("isExternal",True): return lk["href"]
    links=event.get("links",[]); return links[0]["href"] if links else "https://www.espn.com/mlb/"

def inning_str(status):
    """Returns e.g. 'Top 7' or 'Bot 3' or 'F/9'"""
    detail = status.get("type",{}).get("shortDetail","")
    return detail

def make_score_item(event):
    try:
        comp  = event["competitions"][0]
        cs    = comp.get("competitors",[])
        st    = event["status"]["type"]["state"]
        det   = event["status"]["type"].get("shortDetail","")
        url   = game_link(event)
        sicon = STATE_ICON.get(st,"")

        if len(cs) >= 2:
            # MLB: away=0, home=1 typically
            away = next((c for c in cs if c.get("homeAway")=="away"), cs[0])
            home = next((c for c in cs if c.get("homeAway")=="home"), cs[1])
            def nm(c):
                t=c.get("team",{})
                return t.get("abbreviation") or t.get("shortDisplayName") or t.get("name","?")
            an,hn = nm(away),nm(home)
            as_,hs = away.get("score",""),home.get("score","")
            icon = home_icon(home.get("team",{}))

            if st=="pre":
                title=f"{sicon}  {an}  @  {hn}"
                sub=f"MLB  ·  {local_time(event.get('date',''))}"
            elif st=="in":
                title=f"{sicon}  {an}  {as_}  –  {hn}  {hs}"
                sub=f"MLB  ·  {det}"
            else:
                winner=next((nm(c) for c in cs if c.get("winner")),None)
                title=f"{sicon}  {an}  {as_}  –  {hn}  {hs}"
                sub=f"MLB  ·  Final"+(f"  ·  {winner} wins" if winner else "")
        else:
            icon=MLB_ICON; title=event.get("name","Game"); sub=f"MLB  ·  {det}"

        return {"title":title,"subtitle":sub,"arg":url,"valid":True,
                "icon":{"path":icon},"_s":st,"_d":event.get("date","")}
    except: return None

def fetch_scores():
    data,_ = fetch_json(f"{ESPN_BASE}/scoreboard", "mlb_scores", SCORE_TTL)
    items  = [make_score_item(e) for e in data.get("events",[])]
    items  = [i for i in items if i]
    items.sort(key=lambda x:(STATE_ORDER.get(x.get("_s",""),3),x.get("_d","")))
    for i in items: i.pop("_s",None); i.pop("_d",None)
    return items or [{"title":"No MLB games today","subtitle":"Check back later","valid":False}]

# Division ID → (display name, league_id)
DIVISION_MAP = {
    200: ("AL West",    103),
    201: ("AL East",    103),
    202: ("AL Central", 103),
    203: ("NL West",    104),
    204: ("NL East",    104),
    205: ("NL Central", 104),
}

# MLB abbreviation → ESPN CDN abbreviation (only entries that differ)
ESPN_ABBREV = {
    "CWS": "chw",   # Chicago White Sox
    "WSH": "wsh",   # Washington Nationals (MLB uses WSH, ESPN same)
    "WAS": "wsh",
    "AZ":  "ari",   # Arizona Diamondbacks
}

def team_logo(abbrev, tid):
    """Download and cache ESPN team logo; fallback to MLB_ICON."""
    espn_abbrev = ESPN_ABBREV.get(abbrev.upper(), abbrev.lower())
    p = os.path.join(CACHE, f"mlb_team_{espn_abbrev}.png")
    if os.path.exists(p):
        return p
    url = f"https://a.espncdn.com/i/teamlogos/mlb/500/{espn_abbrev}.png"
    return download_logo(url, f"mlb_team_{espn_abbrev}") or MLB_ICON

def next_fixtures_mlb():
    """Build {team_id: 'Next: OPP (H/A)  Date'} for all MLB teams."""
    upcoming_map = {}
    try:
        from datetime import timedelta, date
        today = date.today()
        # Search up to 3 weeks ahead in 2-week windows
        for offset in range(0, 3):
            if len(upcoming_map) >= 30: break   # all 30 teams found
            start = today + timedelta(days=offset * 7)
            end   = start + timedelta(days=13)
            url = (f"https://statsapi.mlb.com/api/v1/schedule"
                   f"?sportId=1&gameType=R&startDate={start}&endDate={end}"
                   f"&hydrate=team")
            data = load_cache(f"mlb_fixtures_{start}", ttl=1800)
            if data is None:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        data = json.loads(r.read())
                    save_cache(f"mlb_fixtures_{start}", data)
                except:
                    continue
            for d_entry in (data.get("dates") or []):
                for game in (d_entry.get("games") or []):
                    state = game.get("status", {}).get("abstractGameState", "")
                    if state not in ("Preview", "Scheduled"): continue
                    teams = game.get("teams", {})
                    home  = teams.get("home", {}).get("team", {})
                    away  = teams.get("away", {}).get("team", {})
                    home_id = str(home.get("id", ""))
                    away_id = str(away.get("id", ""))
                    # Short name: abbreviation or first word of name
                    def short(t):
                        ab = t.get("abbreviation","")
                        if ab: return ab
                        return t.get("name","?").split()[-1]   # e.g. "Athletics"
                    dt_raw = game.get("gameDate","")
                    try:
                        dt = datetime.fromisoformat(dt_raw.replace("Z","+00:00"))
                        date_fmt = dt.astimezone().strftime("%a %d %b")
                    except: date_fmt = ""
                    if home_id and home_id not in upcoming_map:
                        upcoming_map[home_id] = f"Next: {short(away)} (H)  {date_fmt}"
                    if away_id and away_id not in upcoming_map:
                        upcoming_map[away_id] = f"Next: {short(home)} (A)  {date_fmt}"
    except: pass
    return upcoming_map

def fetch_standings():
    """Fetch MLB standings from the official MLB Stats API, grouped by division."""
    from datetime import date
    season = date.today().year
    url = (f"https://statsapi.mlb.com/api/v1/standings"
           f"?leagueId=103,104&season={season}&standingsTypes=regularSeason"
           f"&hydrate=team,division,league")
    key = f"mlb_standings_{season}"

    try:
        data, _ = fetch_json(url, key, STANDING_TTL)
    except Exception as ex:
        return [{"title": "⚠️  MLB Standings", "subtitle": f"Error: {ex}", "valid": False,
                 "icon": {"path": MLB_ICON}}]

    records = data.get("records", [])
    if not records:
        return [{"title": "⚠️  MLB Standings", "subtitle": "No data returned", "valid": False,
                 "icon": {"path": MLB_ICON}}]

    next_map = next_fixtures_mlb()

    # Sort AL (103) before NL (104), then West → East → Central within each league
    DIV_ORDER = {200: 0, 201: 1, 202: 2, 203: 3, 204: 4, 205: 5}
    def sort_key(r):
        div_id = r.get("division", {}).get("id", 999)
        return DIV_ORDER.get(div_id, 99)

    items   = []
    cur_lg  = None  # track which league we're in to insert AL/NL headers

    for record in sorted(records, key=sort_key):
        div_id   = record.get("division", {}).get("id", 0)
        div_info = DIVISION_MAP.get(div_id)
        if div_info:
            div_name, league_id = div_info
        else:
            # Fallback: read name from API response
            div_name   = record.get("division", {}).get("name", "Division")
            league_id  = record.get("league",   {}).get("id",   999)

        # Insert league header when we switch from AL → NL
        league_label = "American League" if league_id == 103 else "National League"
        if league_id != cur_lg:
            cur_lg = league_id
            items.append({"title": f"━━━  {league_label}  ━━━",
                          "subtitle": "", "valid": False, "icon": {"path": MLB_ICON}})

        items.append({"title": f"── {div_name} ──",
                      "subtitle": "", "valid": False, "icon": {"path": MLB_ICON}})

        team_records = record.get("teamRecords", [])
        team_records.sort(key=lambda t: int(t.get("divisionRank", "99") or 99))

        for tr in team_records:
            try:
                team   = tr.get("team", {})
                tname  = team.get("name", "?")
                abbrev = team.get("abbreviation", "")
                tid    = str(team.get("id", ""))
                rank   = tr.get("divisionRank", "?")
                w      = tr.get("wins", 0)
                l      = tr.get("losses", 0)
                pct    = tr.get("winningPercentage", tr.get("pct", ""))
                gb     = tr.get("gamesBack", "-")
                streak = tr.get("streak", {}).get("streakCode", "")

                title = f"{rank}.  {tname}"
                sub   = f"W {w}  L {l}  ·  {pct}"
                if gb and gb not in ("-", "0", "0.0"):
                    sub += f"  ·  GB {gb}"
                if streak:
                    sub += f"  ·  {streak}"
                next_str = next_map.get(tid, "")
                if next_str:
                    sub += f"  |  {next_str}"

                link = f"https://www.espn.com/mlb/team/_/abbrev/{abbrev.lower()}"
                icon = team_logo(abbrev, tid)

                items.append({"title": title, "subtitle": sub, "arg": link,
                              "valid": True, "icon": {"path": icon},
                              "variables": {
                                  "mlbTeamId":  tid,
                                  "teamName":   tname,
                                  "teamAbbrev": abbrev,
                                  "divName":    div_name,
                                  "divRank":    str(rank),
                                  "wins":       str(w),
                                  "losses":     str(l),
                                  "pct":        str(pct),
                                  "gb":         str(gb),
                                  "streak":     str(streak),
                              }})
            except:
                continue

    return items or [{"title": "No standings data", "valid": False, "icon": {"path": MLB_ICON}}]

def main():
    try:
        mode = sys.argv[1].strip().lower() if len(sys.argv)>1 else ""
        if mode == "standings":
            items = fetch_standings()
        else:
            items = fetch_scores()
    except Exception as ex:
        import traceback
        items = [{"title":"⚠️  MLB Error","subtitle":str(ex),"valid":False,
                  "text":{"copy":traceback.format_exc(),"largetype":traceback.format_exc()}}]
    print(json.dumps({"items":items}))

main()
