#!/usr/bin/env python3
"""
ScoreBoard — scores.py
Handles two modes based on arguments:
  scores.py [league]        → scores (no arg = all leagues)
  scores.py table [league]  → standings (no arg = league picker)

Leagues: epl · bundesliga · laliga · seriea · ligue1
"""
import sys, json, os, urllib.request, time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

LEAGUES = {
    "ENG.1":   ("Premier League",   "leagues/epl.svg"),
    "GER.1":   ("Bundesliga",       "leagues/bundesliga.svg"),
    "ESP.1":   ("La Liga",          "leagues/laliga.svg"),
    "ITA.1":   ("Serie A",          "leagues/seriea.svg"),
    "FRA.1":   ("Ligue 1",          "leagues/ligue1.svg"),
    "uefa.champions": ("Champions League", "leagues/ucl.svg"),
    "uefa.europa":    ("Europa League",    "leagues/uel.svg"),
}
# Keyword → slug
ALIASES = {
    "epl":"ENG.1","premier":"ENG.1","england":"ENG.1","eng":"ENG.1",
    "bundesliga":"GER.1","german":"GER.1","ger":"GER.1","germany":"GER.1",
    "laliga":"ESP.1","la liga":"ESP.1","spain":"ESP.1","esp":"ESP.1","liga":"ESP.1",
    "seriea":"ITA.1","serie a":"ITA.1","italy":"ITA.1","ita":"ITA.1","serie":"ITA.1",
    "ligue1":"FRA.1","ligue 1":"FRA.1","france":"FRA.1","fra":"FRA.1","french":"FRA.1",
    "ucl":"uefa.champions","champions":"uefa.champions","champions league":"uefa.champions","cl":"uefa.champions",
    "uel":"uefa.europa","europa":"uefa.europa","europa league":"uefa.europa","el":"uefa.europa",
}
ALL_SLUGS = list(LEAGUES.keys())

ESPN_SOCCER = "https://site.api.espn.com/apis/site/v2/sports/soccer"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
STATE_ICON  = {"pre":"🕐","in":"🔴","post":"✅"}
STATE_ORDER = {"in":0,"pre":1,"post":2}

CACHE = os.environ.get("alfred_workflow_cache",
        os.path.join(os.path.expanduser("~"), ".cache", "scoreboard_logos"))
os.makedirs(CACHE, exist_ok=True)
SCORE_TTL = int(os.environ.get("score_refresh","60"))
STANDING_TTL = 6*3600

def cache_path(k): return os.path.join(CACHE, k.replace("/","_")+".json")
def load_cache(k,ttl=None):
    try:
        p=cache_path(k)
        if ttl is None or time.time()-os.path.getmtime(p)<ttl:
            with open(p) as f: return json.load(f)
    except: pass
def save_cache(k,data):
    try:
        with open(cache_path(k),"w") as f: json.dump(data,f)
    except: pass
def fetch_json(url,key,ttl):
    c=load_cache(key,ttl)
    if c is not None: return c,False
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=8) as r: data=json.loads(r.read())
        save_cache(key,data); return data,False
    except Exception as ex:
        stale=load_cache(key)
        if stale is not None: return stale,True
        raise ex
def download_logo(url,tid):
    if not url or not tid: return None
    p=os.path.join(CACHE,f"{tid}.png")
    if not os.path.exists(p):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA})
            with urllib.request.urlopen(req,timeout=5) as r:
                with open(p,"wb") as f: f.write(r.read())
        except: return None
    return p
def home_icon(ht,li): return download_logo(ht.get("logo",""),ht.get("id","")) or li

def last_name(s):
    parts=s.strip().split(); return parts[-1] if parts else s

def events_str(comp):
    # goal_times: {player_name: [time1, time2, ...]}
    from collections import OrderedDict
    goal_times = OrderedDict()
    yellows = 0; reds = 0
    for d in (comp.get("details") or []):
        dtype = (d.get("type") or {}).get("text","").lower()
        clock = (d.get("clock") or {}).get("displayValue","")
        ps    = d.get("athletesInvolved") or []
        player = last_name(ps[0].get("shortName", ps[0].get("displayName","?")) if ps else "?")
        if "goal" in dtype and "own" not in dtype:
            goal_times.setdefault(player, []).append(clock)
        elif "own goal" in dtype:
            goal_times.setdefault(player + "(OG)", []).append(clock)
        elif "yellow card" in dtype: yellows += 1
        elif "red card"    in dtype: reds    += 1
    parts = []
    if goal_times:
        entries = [f"{p} {' '.join(ts)}" for p, ts in goal_times.items()]
        parts.append("⚽ " + " · ".join(entries))
    cards = ""
    if yellows: cards += f"🟨 {yellows}"
    if reds:    cards += f"  🟥 {reds}"
    if cards:   parts.append(cards.strip())
    return "  |  ".join(parts)

def local_time(s):
    try:
        dt=datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.astimezone().strftime("%-I:%M %p")
    except: return s

def game_link(e):
    for lk in e.get("links",[]):
        if not lk.get("isExternal",True): return lk["href"]
    links=e.get("links",[]); return links[0]["href"] if links else "https://www.espn.com"

def make_score_item(event,lname,licon):
    try:
        comp=event["competitions"][0]; cs=comp.get("competitors",[])
        st=event["status"]["type"]["state"]; det=event["status"]["type"].get("shortDetail","")
        url=game_link(event); sicon=STATE_ICON.get(st,"")
        if len(cs)>=2:
            hc,ac=cs[0],cs[1]
            def nm(c):
                t=c.get("team",{}); return t.get("abbreviation") or t.get("shortDisplayName") or t.get("name","?")
            hn,an=nm(hc),nm(ac); hs,as_=hc.get("score",""),ac.get("score","")
            icon=home_icon(hc.get("team",{}),licon); ev=events_str(comp)
            if st=="pre":   title=f"{sicon}  {hn}  vs  {an}"; sub=f"{lname}  ·  {local_time(event.get('date',''))}"
            elif st=="in":  title=f"{sicon}  {hn}  {hs}  –  {an}  {as_}"; sub=f"{lname}  ·  {det}"; sub+=(f"  |  {ev}" if ev else "")
            else:
                winner=next((nm(c) for c in cs if c.get("winner")),None)
                title=f"{sicon}  {hn}  {hs}  –  {an}  {as_}"
                sub=f"{lname}  ·  Full Time"+(f"  ·  {winner} wins" if winner else "")
                if ev: sub+=f"  |  {ev}"
                sub=sub or f"{lname}  ·  Full Time"
        else: icon=licon; title=event.get("name","Match"); sub=f"{lname}  ·  {det}"
        return {"title":title,"subtitle":sub,"arg":url,"valid":True,"icon":{"path":icon},"_s":st,"_d":event.get("date","")}
    except: return None

def fetch_scores(slug):
    ln,li=LEAGUES[slug]
    try:
        data,stale=fetch_json(f"{ESPN_SOCCER}/{slug}/scoreboard",f"scores_{slug}",SCORE_TTL)
        items=[make_score_item(e,ln,li) for e in data.get("events",[])]
        return [i for i in items if i]
    except Exception as ex:
        return [{"title":f"⚠️  {ln}","subtitle":str(ex),"valid":False,"icon":{"path":li},"_s":"z","_d":""}]

def all_scores(slugs):
    items=[]
    with ThreadPoolExecutor(max_workers=5) as pool:
        for r in as_completed([pool.submit(fetch_scores,s) for s in slugs]): items.extend(r.result())
    items.sort(key=lambda x:(STATE_ORDER.get(x.get("_s",""),3),x.get("_d","")))
    for i in items: i.pop("_s",None); i.pop("_d",None)
    return items or [{"title":"No matches today","subtitle":"No games scheduled","valid":False}]

def query_to_slug(q):
    q=q.strip().lower()
    if not q: return None
    for key,slug in ALIASES.items():
        if key in q: return slug
    return None

# ── Standings ──────────────────────────────────────────────────────────────────
def find_entries(obj,depth=0):
    if depth>6: return []
    if isinstance(obj,list):
        if obj and isinstance(obj[0],dict) and "team" in obj[0] and "stats" in obj[0]: return obj
        for item in obj:
            r=find_entries(item,depth+1)
            if r: return r
    elif isinstance(obj,dict):
        if "entries" in obj and isinstance(obj["entries"],list):
            r=find_entries(obj["entries"],depth+1); 
            if r: return r
        for v in obj.values():
            r=find_entries(v,depth+1)
            if r: return r
    return []

FAV = os.environ.get("fav_team","").strip().lower()

def next_fixtures_from_scoreboard(slug):
    """Build team_id → next fixture string using date-range scoreboard ( technique)."""
    upcoming_map = {}
    try:
        from datetime import timedelta
        today = datetime.now()
        # Search up to 4 weeks ahead in 2-week windows
        for week_offset in range(0, 4):
            if upcoming_map:
                # If we already have entries, just do one more window to catch all teams
                if week_offset > 1: break
            start = today + timedelta(days=week_offset*7)
            end   = start + timedelta(days=13)
            d1 = start.strftime("%Y%m%d")
            d2 = end.strftime("%Y%m%d")
            url = f"{ESPN_SOCCER}/{slug}/scoreboard?dates={d1}-{d2}"
            data, _ = fetch_json(url, f"sb_fix_{slug}_{d1}", 3600)
            for event in (data.get("events") or []):
                comp = (event.get("competitions") or [{}])[0]
                st   = comp.get("status",{}).get("type",{}).get("state","")
                if st != "pre": continue
                cs = comp.get("competitors", [])
                if len(cs) < 2: continue
                try:
                    dt = datetime.fromisoformat(event.get("date","").replace("Z","+00:00"))
                    date_fmt = dt.astimezone().strftime("%a %d %b")
                except: date_fmt = ""
                for i, my in enumerate(cs):
                    op   = cs[1-i]
                    tid  = str(my.get("team",{}).get("id",""))
                    oabb = (op.get("team",{}).get("abbreviation") or
                            op.get("team",{}).get("shortDisplayName","?"))
                    ha   = "H" if my.get("homeAway","") == "home" else "A"
                    if tid and tid not in upcoming_map:
                        upcoming_map[tid] = f"Next: {oabb} ({ha})  {date_fmt}"
    except: pass
    return upcoming_map

def fetch_standings(slug):
    ln,li=LEAGUES[slug]; data=None; last_err=""
    for url in [f"https://site.api.espn.com/apis/v2/sports/soccer/{slug}/standings",
                f"{ESPN_SOCCER}/{slug}/standings"]:
        try: data,_=fetch_json(url,f"standings_{slug}",STANDING_TTL); break
        except Exception as ex: last_err=str(ex)
    if data is None:
        return [{"title":f"⚠️  {ln} Table","subtitle":f"Network error: {last_err}","valid":False,"icon":{"path":li}}]
    entries=find_entries(data)
    if not entries:
        return [{"title":f"⚠️  {ln} Table","subtitle":"No standings data","valid":False,"icon":{"path":li}}]
    next_map = next_fixtures_from_scoreboard(slug)
    items=[]
    for entry in entries:
        try:
            team=entry.get("team",{}); tname=team.get("displayName") or team.get("name","?"); tid=team.get("id","")
            logos=team.get("logos") or []
            logo_url=logos[0].get("href","") if isinstance(logos,list) and logos else team.get("logo","")
            sv={}
            for s in entry.get("stats",[]):
                sv[s.get("name","") or s.get("abbreviation","")]=s.get("displayValue","") or str(int(s.get("value",0)) if isinstance(s.get("value"),float) else "")
            def g(*keys):
                for k in keys:
                    if k in sv: return sv[k]
                return "0"
            rank=int(float(g("rank","standing","rankTeam") or 0))
            pts=g("points","PTS","pts"); gp=g("gamesPlayed","GP","played")
            w=g("wins","W"); d=g("draws","ties","D","T"); l=g("losses","L")
            gf=g("pointsFor","goalsFor","GF"); ga=g("pointsAgainst","goalsAgainst","GA")
            gd_v=g("pointDifferential","goalDifference","GD","diff")
            try: gd_i=int(float(gd_v)); gd_str=f"+{gd_i}" if gd_i>0 else str(gd_i)
            except: gd_str=str(gd_v)
            star="  ★" if FAV and FAV in tname.lower() else ""
            title=f"{rank}.  {tname}{star}"
            next_str = next_map.get(str(tid), "")
            sub=f"Pts {pts}  ·  {gp} played  ·  W{w} D{d} L{l}  ·  GD {gd_str}  ·  {gf}:{ga}"
            if next_str: sub += f"  |  {next_str}"
            link=next((lk.get("href","") for lk in (team.get("links") or []) if not lk.get("isExternal",True)),"https://www.espn.com")
            icon=download_logo(logo_url,tid) or li
            items.append({"title":title,"subtitle":sub,"arg":link,"valid":True,"icon":{"path":icon},
                "variables":{"teamId":tid,"teamName":tname,"slug":slug,"leagueName":ln,
                             "pts":pts,"gp":gp,"w":w,"d":d,"l":l,"gf":gf,"ga":ga,"gd":gd_str,"rank":str(rank)}})
        except: continue
    return items or [{"title":f"No standings for {ln}","valid":False,"icon":{"path":li}}]

# ── League picker (shown when `table` is typed with no arg) ───────────────────
def league_picker():
    return {"items":[
        {"title":ln, "subtitle":f"Type  table {kw}  to view standings",
         "autocomplete":f"{kw} ", "arg":"", "valid":False,
         "icon":{"path":icon}}
        for (kw,slug),(_,(ln,icon)) in zip(
            [("epl","ENG.1"),("bundesliga","GER.1"),("laliga","ESP.1"),("seriea","ITA.1"),("ligue1","FRA.1")],
            [LEAGUES[s] for s in ALL_SLUGS]
        )
    ]}

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    try:
        # Args: scores.py [slug] [table]
        # e.g.  scores.py           → all scores
        #        scores.py ENG.1     → EPL scores
        #        scores.py ENG.1 table → EPL standings
        args = [a.strip() for a in sys.argv[1:] if a.strip()]
        slug  = args[0] if args and args[0] in LEAGUES else None
        table = len(args) >= 2 and args[1].lower() == "table"

        if table and slug:
            items = fetch_standings(slug)
        elif slug:
            items = all_scores([slug])
        else:
            items = all_scores(ALL_SLUGS)

        sys.stdout.write(json.dumps({"items": items}))
    except Exception as ex:
        sys.stdout.write(json.dumps({"items": [{"title": "⚠️  Error", "subtitle": str(ex), "valid": False}]}))

main()
