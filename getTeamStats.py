#!/usr/bin/env python3
import os, json, sys, urllib.request, time
from datetime import datetime

UA    = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
CACHE = os.environ.get("alfred_workflow_cache",
        os.path.join(os.path.expanduser("~"), ".cache", "scoreboard_logos"))
os.makedirs(CACHE, exist_ok=True)
SCHED_TTL = 3600

team_id     = os.environ.get("teamId","")
team_name   = os.environ.get("teamName","Unknown Team")
slug        = os.environ.get("slug","ENG.1")
league_name = os.environ.get("leagueName","")
pts  = os.environ.get("pts","0");  gp = os.environ.get("gp","0")
w    = os.environ.get("w","0");    d  = os.environ.get("d","0")
l    = os.environ.get("l","0");    gf = os.environ.get("gf","0")
ga   = os.environ.get("ga","0");   gd = os.environ.get("gd","0")
rank = os.environ.get("rank","?")

def safe(a,b,dec=2):
    try: return round(int(a)/int(b),dec) if int(b)>0 else 0.0
    except: return 0.0
def pct(a,b):
    try: return f"{round(int(a)/int(b)*100)}%" if int(b)>0 else "0%"
    except: return "—"
def ordinal(n):
    try:
        n=int(n); sfx=["th","st","nd","rd"]
        s=sfx[n%10] if n%10<=3 and n not in [11,12,13] else 'th'; return f'{n}{s}'
    except: return str(n)

gp_i=max(int(gp),1)
ppg=safe(pts,gp_i); gfpg=safe(gf,gp_i); gapg=safe(ga,gp_i)
wr=pct(w,gp_i); dr=pct(d,gp_i); lr=pct(l,gp_i)

def cache_path(k): return os.path.join(CACHE, k.replace("/","_")+".json")

def fetch_url(url, key, ttl):
    cp=cache_path(key)
    try:
        if time.time()-os.path.getmtime(cp)<ttl:
            with open(cp) as f: return json.load(f)
    except: pass
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=10) as r: data=json.loads(r.read())
        try:
            with open(cp,"w") as f: json.dump(data,f)
        except: pass
        return data
    except:
        try:
            with open(cp) as f: return json.load(f)
        except: return None

def local_dt(s):
    try:
        dt=datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.astimezone().strftime("%a %d %b  ·  %-I:%M %p")
    except: return s

def get_score(c):
    s=c.get("score")
    if s is None: return 0
    if isinstance(s,(int,float)): return int(s)
    if isinstance(s,dict):
        v=s.get("value") or s.get("displayValue") or 0
        try: return int(float(v))
        except: return 0
    try: return int(float(str(s)))
    except: return 0

def get_winner(c):
    w=c.get("winner")
    if isinstance(w,bool): return w
    if isinstance(w,str): return w.lower()=="true"
    return bool(w)

def analyse(data):
    """Returns dict with home/away splits, clean sheets, next 5 fixtures."""
    if not data: return None

    events = data.get("events",[])
    events.sort(key=lambda e: e.get("date",""))

    completed=[]; upcoming=[]
    for e in events:
        comp=(e.get("competitions") or [{}])[0]
        st=comp.get("status",{}).get("type",{}).get("state","")
        if st=="post":  completed.append(e)
        elif st=="pre": upcoming.append(e)

    # ── Parse completed matches ───────────────────────────────────────────────
    results=[]
    for e in completed:
        try:
            comp=(e.get("competitions") or [{}])[0]
            cs=comp.get("competitors",[])
            tid=str(team_id).strip()
            my=next((c for c in cs if str(c.get("team",{}).get("id","")).strip()==tid),None)
            op=next((c for c in cs if str(c.get("team",{}).get("id","")).strip()!=tid),None)
            if not my or not op: continue
            ms=get_score(my); os_=get_score(op)
            ha=my.get("homeAway","home")
            res="W" if get_winner(my) else ("L" if get_winner(op) else "D")
            oname=(op.get("team",{}).get("abbreviation") or
                   op.get("team",{}).get("shortDisplayName","?"))
            results.append({"res":res,"gf":ms,"ga":os_,"ha":ha,"opp":oname})
        except: continue

    if not results: return None

    home=[r for r in results if r["ha"]=="home"]
    away=[r for r in results if r["ha"]!="home"]

    def rec(lst):
        ww=sum(1 for r in lst if r["res"]=="W")
        dd=sum(1 for r in lst if r["res"]=="D")
        ll=sum(1 for r in lst if r["res"]=="L")
        return ww,dd,ll,sum(r["gf"] for r in lst),sum(r["ga"] for r in lst)

    tot=len(results)
    hw,hd,hl,hgf,hga=rec(home)
    aw,ad,al,agf,aga=rec(away)
    cs_n  = sum(1 for r in results if r["ga"]==0)
    fts   = sum(1 for r in results if r["gf"]==0)
    btts  = sum(1 for r in results if r["gf"]>0 and r["ga"]>0)
    wins  = [(r["gf"]-r["ga"],r) for r in results if r["res"]=="W"]
    losses= [(r["ga"]-r["gf"],r) for r in results if r["res"]=="L"]
    def fmt_r(r): return f"{r['gf']}–{r['ga']} vs {r['opp']} ({'H' if r['ha']=='home' else 'A'})"
    big_win  = fmt_r(max(wins,  key=lambda x:x[0])[1]) if wins  else None
    big_loss = fmt_r(max(losses,key=lambda x:x[0])[1]) if losses else None

    # ── Next 5 fixtures ───────────────────────────────────────────────────────
    next5=[]
    tid=str(team_id).strip()
    for e in upcoming[:5]:
        try:
            comp=(e.get("competitions") or [{}])[0]
            cs=comp.get("competitors",[])
            # Try ID match first, then fall back to any 2-competitor event
            my=next((c for c in cs if str(c.get("team",{}).get("id","")).strip()==tid),None)
            if not my and len(cs)>=2:
                # Fallback: check home/away field or just use first competitor as "my"
                # For schedule endpoint, events only include this team's games
                my=cs[0]; cs_others=cs[1:]
            else:
                cs_others=[c for c in cs if c is not my]
            op=cs_others[0] if cs_others else None
            if op:
                ha="Home" if (my or {}).get("homeAway","")=="home" else "Away"
                opp=(op.get("team",{}).get("displayName") or
                     op.get("team",{}).get("shortDisplayName") or
                     op.get("team",{}).get("name","?"))
                venue=(comp.get("venue") or {}).get("fullName","")
                next5.append({"ha":ha,"opp":opp,"date":local_dt(e.get("date","")),"venue":venue})
        except: continue
    # If schedule had no upcoming events, try fetching next season's early fixtures
    # by checking events list length as diagnostic
    _upcoming_count = len(upcoming)

    return {
        "home":(hw,hd,hl,hgf,hga), "away":(aw,ad,al,agf,aga),
        "tot":tot, "cs":cs_n, "fts":fts, "btts":btts,
        "big_win":big_win, "big_loss":big_loss,
        "next5":next5,
    }

def build_md(stats, err=None):
    PAD=22
    def row(l,v): return f"{l}:{' '*max(1,PAD-len(l))}{v}"

    lines=[f"# {team_name}"]
    if league_name:
        lines.append(f"*{league_name}  ·  {ordinal(rank)} Place*\n")

    lines+=["### Season Overview","```",
        row("Points",    f"{pts}  ({ppg} per game)"),
        row("Record",    f"W{w}  D{d}  L{l}  ({gp} played)"),
        row("Win Rate",  f"{wr}   Draw: {dr}   Loss: {lr}"),
        row("Goals For", f"{gf}  ({gfpg} per game)"),
        row("Goals Agst",f"{ga}  ({gapg} per game)"),
        row("Goal Diff", gd),"```"]

    if err:
        lines+=["",f"*⚠️ {err}*"]

    if stats:
        hw,hd,hl,hgf,hga=stats["home"]
        aw,ad,al,agf,aga=stats["away"]
        hn=hw+hd+hl; an=aw+ad+al; tot=stats["tot"]

        lines+=["","### Home vs Away","```",
            row("Home",f"W{hw} D{hd} L{hl}  ·  {hgf}:{hga}  ({hn} games)"),
            row("Away",f"W{aw} D{ad} L{al}  ·  {agf}:{aga}  ({an} games)"),"```"]

        lines+=["","### Attack & Defence","```",
            row("Clean Sheets",    f"{stats['cs']}  ({pct(stats['cs'],tot)} of games)"),
            row("Failed to Score", f"{stats['fts']}  ({pct(stats['fts'],tot)} of games)"),
            row("Both Teams Score",f"{stats['btts']}  ({pct(stats['btts'],tot)} of games)")]
        if stats["big_win"]:  lines.append(row("Biggest Win",  stats["big_win"]))
        if stats["big_loss"]: lines.append(row("Biggest Loss", stats["big_loss"]))
        lines.append("```")

        if stats["next5"]:
            lines+=["","### Next 5 Fixtures"]
            for fix in stats["next5"]:
                venue_str = f"  ·  {fix['venue']}" if fix.get("venue") else ""
                lines.append(f"📅  {fix['ha']}  vs  {fix['opp']}")
                lines.append(f"     {fix['date']}{venue_str}")


    return "\n".join(lines)

def main():
    stats=None; err=None
    try:
        if not team_id:
            err="No team selected"
        else:
            # Step 1: get completed matches from team schedule (for home/away splits etc)
            sched_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/teams/{team_id}/schedule"
            sched_data = fetch_url(sched_url, f"sched_{slug}_{team_id}", SCHED_TTL)
            stats = analyse(sched_data)
            if stats is None:
                err = "Schedule data unavailable"

            # Step 2: get upcoming fixtures using scoreboard with future date ranges
            
            if stats is not None and not stats["next5"]:
                from datetime import timedelta
                today = datetime.now()
                fixtures = []
                # Search up to 60 days ahead in 2-week windows
                for week_offset in range(0, 18):
                    if len(fixtures) >= 5: break
                    start = today + timedelta(days=week_offset*14)
                    end   = start + timedelta(days=13)
                    d1 = start.strftime("%Y%m%d")
                    d2 = end.strftime("%Y%m%d")
                    sb_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={d1}-{d2}"
                    sb_data = fetch_url(sb_url, f"sb_{slug}_{d1}", 3600)
                    if not sb_data: continue
                    tid_s = str(team_id).strip()
                    for event in (sb_data.get("events") or []):
                        if len(fixtures) >= 5: break
                        comp = (event.get("competitions") or [{}])[0]
                        st   = comp.get("status",{}).get("type",{}).get("state","")
                        if st != "pre": continue
                        cs = comp.get("competitors",[])
                        my = next((c for c in cs if str(c.get("team",{}).get("id","")).strip()==tid_s), None)
                        op = next((c for c in cs if str(c.get("team",{}).get("id","")).strip()!=tid_s), None)
                        if my and op:
                            ha  = "Home" if my.get("homeAway","")=="home" else "Away"
                            opp = (op.get("team",{}).get("displayName") or
                                   op.get("team",{}).get("shortDisplayName","?"))
                            venue = (comp.get("venue") or {}).get("fullName","")
                            date_s = local_dt(event.get("date",""))
                            key = f"{opp}_{event.get('date','')[:10]}"
                            if not any(f.get("_key")==key for f in fixtures):
                                fixtures.append({"ha":ha,"opp":opp,"date":date_s,
                                    "venue":venue,"_key":key})
                if fixtures:
                    for f in fixtures: f.pop("_key", None)
                    stats["next5"] = fixtures
    except Exception as ex:
        err=str(ex)

    try:
        md=build_md(stats,err)
    except Exception as ex:
        md=f"# {team_name}\n\nError: {ex}"

    sys.stdout.write(json.dumps({"response":md,"footer":"⌘↩  Open team page in browser"}))

main()
