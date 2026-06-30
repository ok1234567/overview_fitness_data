import os, math
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, redirect, request, session, jsonify, render_template_string, send_from_directory
import requests

app = Flask(__name__)
app.secret_key = "stride-local-secret-key-do-not-share"

def CLIENT_ID():     return _read_env("STRAVA_CLIENT_ID")
def CLIENT_SECRET(): return _read_env("STRAVA_CLIENT_SECRET")
def _read_env(key, default=""):
    val = os.environ.get(key, "")
    if val: return val
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, ".env")) as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return default

REDIRECT_URI = _read_env("STRIDE_REDIRECT_URI", "https://ja12sr34.pythonanywhere.com/callback")

STRAVA_AUTH_URL  = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE  = "https://www.strava.com/api/v3"

GOOGLE_CLIENT_ID     = lambda: _read_env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = lambda: _read_env("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = "https://ja12sr34.pythonanywhere.com/google/callback"

GOOGLE_AUTH_URL   = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL  = "https://oauth2.googleapis.com/token"
GOOGLE_CAL_BASE   = "https://www.googleapis.com/calendar/v3"

GOOGLE_SCOPES = "https://www.googleapis.com/auth/calendar.readonly"

# ── Helpers ───────────────────────────────────────────────────────────────────
# ── Simple in-memory cache ───────────────────────────────────────────────────
_cache = {}
CACHE_TTL = 900  # 15 minutes

def cache_get(key):
    entry = _cache.get(key)
    if entry and (datetime.now() - entry["ts"]).seconds < CACHE_TTL:
        return entry["val"]
    return None

def cache_set(key, val):
    _cache[key] = {"val": val, "ts": datetime.now()}

def m_to_km(m):
    return round(m / 1000.0, 2)

def mps_to_pace(mps):
    if not mps or mps == 0: return "—"
    spk = 1000.0 / mps  # Segundos por quilómetro
    return f"{int(spk//60)}:{int(spk%60):02d}"

def s_to_hms(s):
    h,m,sec = int(s//3600),int((s%3600)//60),int(s%60)
    return f"{h}h {m}m" if h else f"{m}m {sec}s"

def elev_m(m):
    return round(m) # Substitui a conversão de pés (ft) para manter a elevação em metros

def get_headers(): return {"Authorization": f"Bearer {session.get('access_token')}"}

def get_google_headers():
    token = session.get("google_access_token")
    if not token:
        return None
    expiry_str = session.get("google_token_expiry", "")
    if expiry_str:
        try:
            expiry = datetime.fromisoformat(expiry_str)
            if datetime.now() >= expiry - timedelta(minutes=5):
                token = _refresh_google_token()
                if not token:
                    return None
        except Exception:
            pass
    return {"Authorization": f"Bearer {token}"}

def _refresh_google_token():
    refresh_token = session.get("google_refresh_token")
    if not refresh_token:
        return None
    try:
        resp = requests.post(GOOGLE_TOKEN_URL, data={
            "client_id":     GOOGLE_CLIENT_ID(),
            "client_secret": GOOGLE_CLIENT_SECRET(),
            "refresh_token": refresh_token,
            "grant_type":    "refresh_token",
        })
        data = resp.json()
        if "access_token" in data:
            session["google_access_token"] = data["access_token"]
            session["google_token_expiry"] = (
                datetime.now() + timedelta(seconds=data.get("expires_in", 3600))
            ).isoformat()
            return data["access_token"]
    except Exception:
        pass
    return None

def fetch_all_runs():
    """Fetch all training activities (not just runs) from Strava."""
    from fuel import TRAINING_TYPES
    activities = []
    for page in range(1, 5):
        resp = requests.get(f"{STRAVA_API_BASE}/athlete/activities",
            headers=get_headers(), params={"per_page":50,"page":page})
        if resp.status_code != 200: break
        data = resp.json()
        activities.extend([a for a in data if a.get("type") in TRAINING_TYPES])
        if len(data) < 50: break
    return activities

def fetch_runs_only():
    """Fetch only running activities from Strava — used for pace/performance metrics."""
    RUN_TYPES = {"Run", "VirtualRun", "TrailRun"}
    activities = []
    for page in range(1, 5):
        resp = requests.get(f"{STRAVA_API_BASE}/athlete/activities",
            headers=get_headers(), params={"per_page":50,"page":page})
        if resp.status_code != 200: break
        data = resp.json()
        activities.extend([a for a in data if a.get("type") in RUN_TYPES])
        if len(data) < 50: break
    return activities

def compute_stats(runs):
    if not runs: return {}
    now = datetime.now()
    week_init = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    for r in runs:
        r["_dt"] = datetime.strptime(r["start_date_local"][:10], "%Y-%m-%d")
    runs.sort(key=lambda r: r["_dt"])

    weeks = defaultdict(lambda: {"runs":[],"miles":0,"time":0,"elev":0})
    for r in runs:
        mon = r["_dt"] - timedelta(days=r["_dt"].weekday())
        key = mon.strftime("%Y-%m-%d")
        weeks[key]["runs"].append(r)
        weeks[key]["miles"] += m_to_km(r["distance"])
        weeks[key]["time"]  += r.get("moving_time", 0)
        weeks[key]["elev"]  += r.get("total_elevation_gain", 0)

    sorted_weeks = sorted(weeks.items(), reverse=True)[:8]
    weekly_table = []
    for wkey, wdata in sorted_weeks:
        dt = datetime.strptime(wkey, "%Y-%m-%d")
        td = sum(r["distance"] for r in wdata["runs"])
        tt = sum(r.get("moving_time",0) for r in wdata["runs"])
        weekly_table.append({
            "week":  dt.strftime("%b %d"), "runs": len(wdata["runs"]),
            "miles": round(wdata["miles"],1), "time": s_to_hms(wdata["time"]),
            "pace":  mps_to_pace(td/tt) if td>0 and tt>0 else "—",
            "elev":  elev_m(wdata["elev"]),
            "run_ids": [r["id"] for r in wdata["runs"]],
            # Full run details for popover — not just IDs
            "run_details": [{
                "id":    r["id"],
                "name":  r.get("name", "Run"),
                "miles": m_to_km(r["distance"]),
                "pace":  mps_to_pace(r.get("average_speed", 0)),
                "date":  r["_dt"].strftime("%a %b %d"),
            } for r in reversed(wdata["runs"])],
        })

    months = defaultdict(lambda: {"miles":0,"runs":0})
    for r in runs:
        key = r["_dt"].strftime("%Y-%m")
        months[key]["miles"] += m_to_km(r["distance"])
        months[key]["runs"]  += 1
    sm = sorted(months.items())[-12:]
    monthly_chart = {
        "labels": [datetime.strptime(m[0],"%Y-%m").strftime("%b '%y") for m in sm],
        "miles":  [round(m[1]["miles"],1) for m in sm],
    }

    sorted_spark_weeks = sorted(weeks.items())[-20:]
    weekly_spark = {
        "labels": [w[0] for w in sorted_spark_weeks],
        "miles":  [round(w[1]["miles"],1) for w in sorted_spark_weeks],
        "run_details": [[{
            "id":    r["id"],
            "name":  r.get("name","Run"),
            "miles": m_to_km(r["distance"]),
            "pace":  mps_to_pace(r.get("average_speed",0)),
            "date":  r["_dt"].strftime("%a %b %d"),
        } for r in reversed(w[1]["runs"])] for w in sorted_spark_weeks],
    }

    pace_runs = [r for r in runs if r.get("average_speed",0)>0][-30:]
    pace_trend = {
        "labels":   [r["_dt"].strftime("%b %d") for r in pace_runs],
        "pace_sec": [round(1609.344/r["average_speed"]) for r in pace_runs],
        "run_ids":  [r["id"] for r in pace_runs],
    }

    buckets = {"<5km":0,"5-10km":0,"10-15km":0,"15-21km":0,"21+km":0}
    for r in runs:
        km = m_to_km(r["distance"])
        if km<5: buckets["<5km"]+=1
        elif km<10: buckets["5-10km"]+=1
        elif km<15: buckets["10-15km"]+=1
        elif km<21: buckets["15-21km"]+=1
        else: buckets["21+km"]+=1
    dist_dist = {"labels":list(buckets.keys()),"counts":list(buckets.values())}

    tw = [r for r in runs if r["_dt"] >= week_init]
    tm = [r for r in runs if r["_dt"] >= now.replace(day=1)]
    ty = [r for r in runs if r["_dt"] >= now.replace(month=1,day=1)]
    def agg(s): return {"runs":len(s),"miles":round(sum(m_to_km(r["distance"]) for r in s),1),"time":s_to_hms(sum(r.get("moving_time",0) for r in s))}

    pr_dist = max(runs, key=lambda r: r["distance"])
    pr_long = {"miles":m_to_km(pr_dist["distance"]),"date":pr_dist["_dt"].strftime("%b %d, %Y"),
               "name":pr_dist.get("name","Run"),"id":pr_dist["id"]}
    pr_5k=pr_10k=pr_hm=None
    for r in runs:
        d,t = r["distance"],r.get("moving_time",0)
        if d>=5000 and t>0:
            p=t/d
            if pr_5k is None or p<pr_5k["p"]: pr_5k={"p":p,"time":t,"date":r["_dt"].strftime("%b %d, %Y"),"id":r["id"]}
        if d>=10000 and t>0:
            p=t/d
            if pr_10k is None or p<pr_10k["p"]: pr_10k={"p":p,"time":t,"date":r["_dt"].strftime("%b %d, %Y"),"id":r["id"]}
        if d>=21097 and t>0:
            p=t/d
            if pr_hm is None or p<pr_hm["p"]: pr_hm={"p":p,"time":t,"date":r["_dt"].strftime("%b %d, %Y"),"id":r["id"]}
    def fmt_pr(pr):
        if not pr: return None
        return {"pace":mps_to_pace(1/pr["p"]),"time":s_to_hms(pr["time"]),"date":pr["date"],"id":pr["id"]}

    run_dates = sorted(set(r["_dt"].date() for r in runs))
    best=cur=1
    for i in range(1,len(run_dates)):
        if (run_dates[i]-run_dates[i-1]).days==1: cur+=1; best=max(best,cur)
        else: cur=1
    today=now.date(); cs=0; check=today
    while check in set(run_dates): cs+=1; check-=timedelta(days=1)
    if cs==0:
        check=today-timedelta(days=1)
        while check in set(run_dates): cs+=1; check-=timedelta(days=1)

    recent=[]
    for r in reversed(runs[-15:]):
        recent.append({
            "id":    r["id"],
            "name":  r.get("name","Run"),
            "date":  r["_dt"].strftime("%a %b %d"),
            "miles": m_to_km(r["distance"]),
            "pace":  mps_to_pace(r.get("average_speed",0)),
            "time":  s_to_hms(r.get("moving_time",0)),
            "elev":  elev_m(r.get("total_elevation_gain",0)),
            "hr":    r.get("average_heartrate","—"),
        })

    return {
        "totals": {"week":agg(tw),"month":agg(tm),"year":agg(ty),
                   "all_runs":len(runs),"all_miles":round(sum(m_to_km(r["distance"]) for r in runs),1)},
        "streaks": {"current":cs,"best":best},
        "prs": {"longest":pr_long,"5k":fmt_pr(pr_5k),"10k":fmt_pr(pr_10k),"half":fmt_pr(pr_hm)},
        "weekly_table":weekly_table,"monthly_chart":monthly_chart,
        "weekly_spark":weekly_spark,"pace_trend":pace_trend,
        "dist_dist":dist_dist,"recent":recent,
    }

# ── Run detail helpers ────────────────────────────────────────────────────────
def decode_polyline(encoded):
    """Decode a Google encoded polyline to list of [lat,lng]."""
    coords, idx, lat, lng = [], 0, 0, 0
    while idx < len(encoded):
        for is_lng in (False, True):
            shift, result = 0, 0
            while True:
                b = ord(encoded[idx]) - 63; idx += 1
                result |= (b & 0x1f) << shift; shift += 5
                if b < 0x20: break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lng: lng += delta
            else: lat += delta
        coords.append([lat/1e5, lng/1e5])
    return coords

def compute_training_load(activity):
    """Estimate training load (TSS proxy) and intensity."""
    moving_time = activity.get("moving_time", 0)
    avg_hr      = activity.get("average_heartrate")
    max_hr      = activity.get("max_heartrate")
    suffer      = activity.get("suffer_score")
    distance    = activity.get("distance", 0)

    # Intensity factor: use HR % of estimated max (198 default)
    est_max_hr = float(_read_env("ATHLETE_ESTIM_MAX_HR", "198"))
    intensity = round((avg_hr / est_max_hr) * 100) if avg_hr else None

    # Trimp-style load estimate
    if avg_hr and moving_time:
        hr_ratio = avg_hr / est_max_hr
        trimp = moving_time / 60 * hr_ratio * (0.64 * math.exp(1.92 * hr_ratio))
        training_load = round(trimp)
    else:
        training_load = None

    # HR zones (% of est_max_hr)
    zones = {"z1":0,"z2":0,"z3":0,"z4":0,"z5":0}
    if avg_hr:
        pct = avg_hr / est_max_hr
        if pct < 0.60:   zones["z1"] = 100
        elif pct < 0.70: zones["z2"] = 100
        elif pct < 0.80: zones["z3"] = 100
        elif pct < 0.90: zones["z4"] = 100
        else:            zones["z5"] = 100

    return {
        "suffer_score":   suffer,
        "training_load":  training_load,
        "intensity_pct":  intensity,
        "avg_hr":         avg_hr,
        "max_hr":         max_hr,
        "hr_zones":       zones,
    }

def process_streams(streams_data):
    """Turn raw Strava stream response into chart-ready arrays sampled every ~100m."""
    # streams_data may be a list OR a dict depending on key_by_type param
    if isinstance(streams_data, dict):
        by_type = {k: v.get("data", []) if isinstance(v, dict) else v
                   for k, v in streams_data.items()}
    else:
        by_type = {}
        for s in streams_data:
            if isinstance(s, dict) and "type" in s:
                by_type[s["type"]] = s.get("data", [])

    dist_raw  = by_type.get("distance", [])
    alt_raw   = by_type.get("altitude", [])
    hr_raw    = by_type.get("heartrate", [])
    vel_raw   = by_type.get("velocity_smooth", [])
    latlng    = by_type.get("latlng", [])

    if not dist_raw:
        return {"latlng": latlng, "distance":[], "elevation":[], "hr":[], "pace":[]}

    # Downsample to ~200 points max for chart performance
    n = len(dist_raw)
    step = max(1, n // 200)
    idx  = list(range(0, n, step))

    def sample(arr): return [arr[i] for i in idx] if arr else []

    dist_mi   = [round(d/1609.344, 3) for d in sample(dist_raw)]
    elev_ft   = [round(a*3.28084) for a in sample(alt_raw)] if alt_raw else []
    hr_pts    = sample(hr_raw)
    pace_pts  = []
    for v in sample(vel_raw):
        if v and v > 0:
            spm = 1609.344 / v
            pace_pts.append(round(spm))  # seconds per mile
        else:
            pace_pts.append(None)

    # Thin latlng for map (max 1000 points)
    map_step   = max(1, len(latlng) // 1000)
    map_coords = latlng[::map_step]

    return {
        "latlng":     map_coords,
        "distance":   dist_mi,
        "elevation":  elev_ft,
        "hr":         hr_pts,
        "pace":       pace_pts,
    }

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if not session.get("access_token"): return render_template_string(LOGIN_PAGE)
    return render_template_string(DASHBOARD_PAGE)

@app.route("/debug/google")
def debug_google():
    return {
        "GOOGLE_REDIRECT_URI": "https://ja12sr34.pythonanywhere.com/google/callback",
        "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID")
    }

@app.route("/login")
def login():
    url = (f"{STRAVA_AUTH_URL}?client_id={CLIENT_ID()}&redirect_uri={REDIRECT_URI}"
           f"&response_type=code&approval_prompt=auto&scope=activity:read_all")
    return redirect(url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code: return "Auth failed", 400
    resp = requests.post(STRAVA_TOKEN_URL, data={
        "client_id":CLIENT_ID(),"client_secret":CLIENT_SECRET(),
        "code":code,"grant_type":"authorization_code"})
    data = resp.json()
    if "access_token" not in data: return f"Token error: {data}", 400
    session["access_token"] = data["access_token"]
    session["athlete"]      = data.get("athlete", {})
    return redirect("/")

@app.route("/api/stats")
def api_stats():
    if not session.get("access_token"): return jsonify({"error":"not authenticated"}), 401
    cache_key = f"stats_{session.get('access_token', '')[:16]}"
    cached = cache_get(cache_key)
    if cached:
        return jsonify(cached)
    stats = compute_stats(fetch_runs_only())
    stats["athlete"] = session.get("athlete", {})
    cache_set(cache_key, stats)
    return jsonify(stats)

@app.route("/api/cache/clear")
def api_cache_clear():
    _cache.clear()
    return jsonify({"ok": True, "message": "Cache cleared — next load will re-fetch from Strava"})

@app.route("/api/run/<int:run_id>")
def api_run(run_id):
    """Full activity detail + decoded route + streams."""
    if not session.get("access_token"):
        return jsonify({"error": "not authenticated"}), 401
    try:
        # Fetch activity detail
        act_resp = requests.get(f"{STRAVA_API_BASE}/activities/{run_id}",
                                headers=get_headers(), params={"include_all_efforts": False})
        if act_resp.status_code != 200:
            return jsonify({"error": f"Strava returned {act_resp.status_code}", "body": act_resp.text[:400]}), act_resp.status_code
        act = act_resp.json()

        # Decode polyline for map fallback
        poly = act.get("map", {}).get("polyline") or act.get("map", {}).get("summary_polyline", "")
        poly_coords = decode_polyline(poly) if poly else []

        # Fetch streams
        streams_resp = requests.get(
            f"{STRAVA_API_BASE}/activities/{run_id}/streams",
            headers=get_headers(),
            params={"keys": "distance,altitude,heartrate,velocity_smooth,latlng", "key_by_type": "false"})
        streams = {}
        if streams_resp.status_code == 200:
            raw = streams_resp.json()
            streams = process_streams(raw)
            if not streams.get("latlng"):
                streams["latlng"] = poly_coords
        else:
            streams = {"latlng": poly_coords, "distance": [], "elevation": [], "hr": [], "pace": []}

        # Build summary
        dt = datetime.strptime(act["start_date_local"][:16], "%Y-%m-%dT%H:%M")
        training = compute_training_load(act)
        splits = []
        for sp in act.get("splits_metric", []):
            mi = sp.get("distance", 0)
            t  = sp.get("moving_time", 0)
            splits.append({
                "split": sp.get("split"),
                "miles": round(mi / 1609.344, 2),
                "pace":  mps_to_pace(mi / t) if mi > 0 and t > 0 else "—",
                "hr":    round(sp["average_heartrate"]) if sp.get("average_heartrate") else "—",
                "elev":  elev_m(sp.get("elevation_difference", 0)),
            })

        summary = {
            "id":           act["id"],
            "name":         act.get("name", "Run"),
            "date":         dt.strftime("%A, %B %d %Y"),
            "time_start":   dt.strftime("%I:%M %p"),
            "miles":        m_to_km(act.get("distance", 0)),
            "moving_time":  s_to_hms(act.get("moving_time", 0)),
            "elapsed_time": s_to_hms(act.get("elapsed_time", 0)),
            "avg_pace":     mps_to_pace(act.get("average_speed", 0)),
            "avg_hr":       round(act["average_heartrate"]) if act.get("average_heartrate") else "—",
            "max_hr":       round(act["max_heartrate"])     if act.get("max_heartrate")     else "—",
            "elev_gain":    elev_m(act.get("total_elevation_gain", 0)),
            "elev_loss":    elev_m(act.get("total_elevation_loss") or 0),
            "calories":     act.get("calories") or act.get("kilojoules", "—"),
            "cadence":      round(act["average_cadence"] * 2) if act.get("average_cadence") else "—",
            "temp_c":       act.get("average_temp", "—"),
            "kudos":        act.get("kudos_count", 0),
            "strava_url":   f"https://www.strava.com/activities/{run_id}",
            "training":     training,
            "splits":       splits,
        }

        return jsonify({"summary": summary, "streams": streams})

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/debug/run/<int:run_id>")
def api_debug_run(run_id):
    """Raw Strava responses — open in browser to diagnose errors."""
    if not session.get("access_token"):
        return jsonify({"error": "not authenticated"}), 401
    act_resp = requests.get(f"{STRAVA_API_BASE}/activities/{run_id}",
                            headers=get_headers(), params={"include_all_efforts": False})
    streams_resp = requests.get(
        f"{STRAVA_API_BASE}/activities/{run_id}/streams",
        headers=get_headers(),
        params={"keys": "distance,altitude,heartrate,velocity_smooth,latlng", "key_by_type": "false"})
    return jsonify({
        "activity_status":  act_resp.status_code,
        "activity_sample":  act_resp.json() if act_resp.status_code == 200 else act_resp.text[:600],
        "streams_status":   streams_resp.status_code,
        "streams_sample":   (streams_resp.json()[:2] if isinstance(streams_resp.json(), list)
                             else streams_resp.json()) if streams_resp.status_code == 200 else streams_resp.text[:600],
    })

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"), filename)

@app.route("/logout")
def logout():
    session.clear(); return redirect("/")

@app.route("/google/login")
def google_login():
    if not session.get("access_token"):
        return redirect("/")
    import urllib.parse
    params = {
        "client_id":     GOOGLE_CLIENT_ID(),
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         GOOGLE_SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
    }
    url = GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)
    return redirect(url)

@app.route("/google/callback")
def google_callback():
    code = request.args.get("code")
    if not code:
        return "Google auth failed — no code returned", 400
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "client_id":     GOOGLE_CLIENT_ID(),
        "client_secret": GOOGLE_CLIENT_SECRET(),
        "code":          code,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "grant_type":    "authorization_code",
    })
    data = resp.json()
    if "access_token" not in data:
        return f"Google token error: {data}", 400
    session["google_access_token"]  = data["access_token"]
    session["google_refresh_token"] = data.get("refresh_token", "")
    session["google_token_expiry"]  = (
        datetime.now() + timedelta(seconds=data.get("expires_in", 3600))
    ).isoformat()
    return redirect("/")

@app.route("/google/disconnect")
def google_disconnect():
    session.pop("google_access_token", None)
    session.pop("google_refresh_token", None)
    session.pop("google_token_expiry", None)
    return redirect("/")

@app.route("/api/google/status")
def api_google_status():
    connected = bool(session.get("google_access_token"))
    return jsonify({"connected": connected})

@app.route("/api/google/calendar/runna")
def api_google_calendar_runna():
    if not session.get("access_token"):
        return jsonify({"error": "not authenticated"}), 401
    headers = get_google_headers()
    if not headers:
        return jsonify({"connected": False, "events": []})
    try:
        cal_resp = requests.get(
            f"{GOOGLE_CAL_BASE}/users/me/calendarList",
            headers=headers
        )
        if cal_resp.status_code == 401:
            session.pop("google_access_token", None)
            return jsonify({"connected": False, "events": []})
        if cal_resp.status_code != 200:
            return jsonify({"error": f"Calendar list error: {cal_resp.status_code}"}), 500
        calendars = cal_resp.json().get("items", [])
        runna_cal = next(
            (c for c in calendars if "runna" in c.get("summary", "").lower()),
            None
        )
        if not runna_cal:
            return jsonify({
                "connected": True,
                "runna_found": False,
                "events": [],
                "message": "No calendar named 'Runna' found."
            })
        cal_id = runna_cal["id"]
        now = datetime.utcnow()
        time_min = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        time_max = (now + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
        events_resp = requests.get(
            f"{GOOGLE_CAL_BASE}/calendars/{cal_id}/events",
            headers=headers,
            params={
                "timeMin":      time_min,
                "timeMax":      time_max,
                "singleEvents": "true",
                "orderBy":      "startTime",
                "maxResults":   30,
            }
        )
        if events_resp.status_code != 200:
            return jsonify({"error": f"Events fetch error: {events_resp.status_code}"}), 500
        raw_events = events_resp.json().get("items", [])
        from fuel import classify_runna_event, DAY_TYPE_COLOR
        parsed = []
        for ev in raw_events:
            title = ev.get("summary", "")
            if not title:
                continue
            start = ev.get("start", {})
            date_str = start.get("date") or start.get("dateTime", "")[:10]
            if not date_str:
                continue
            day_type = classify_runna_event(title)
            parsed.append({
                "date":     date_str,
                "title":    title,
                "day_type": day_type,
                "color":    DAY_TYPE_COLOR.get(day_type, "yellow"),
            })
        return jsonify({
            "connected":     True,
            "runna_found":   True,
            "calendar_name": runna_cal.get("summary", "Runna"),
            "events":        parsed,
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route("/api/fuel/plan")
def api_fuel_plan():
    if not session.get("access_token"):
        return jsonify({"error": "not authenticated"}), 401
    try:
        from fuel import classify_day, plan_day, DAY_TYPE_COLOR

        weight_kg = float(_read_env("ATHLETE_WEIGHT_KG", "73"))
        height_cm = float(_read_env("ATHLETE_HEIGHT_CM", "180"))
        age = int(_read_env("ATHLETE_AGE", "27"))

        # ── Past 7 days from Strava ──────────────────────────────────────
        runs = fetch_all_runs()
        now  = datetime.now()
        for r in runs:
            r["_dt"] = datetime.strptime(r["start_date_local"][:10], "%Y-%m-%d")

        # Build a lookup: date string → run
        run_by_date = {}
        for r in runs:
            ds = r["_dt"].strftime("%Y-%m-%d")
            # keep the longest run if multiple on same day
            if ds not in run_by_date or r["distance"] > run_by_date[ds]["distance"]:
                run_by_date[ds] = r

        # ── Next 14 days from Runna calendar ────────────────────────────
        runna_by_date = {}
        google_connected = bool(session.get("google_access_token"))
        if google_connected:
            headers = get_google_headers()
            if headers:
                cal_resp = requests.get(
                    f"{GOOGLE_CAL_BASE}/users/me/calendarList",
                    headers=headers
                )
                if cal_resp.status_code == 200:
                    calendars = cal_resp.json().get("items", [])
                    runna_cal = next(
                        (c for c in calendars if "runna" in c.get("summary", "").lower()),
                        None
                    )
                    if runna_cal:
                        from fuel import classify_runna_event
                        time_min = now.strftime("%Y-%m-%dT%H:%M:%SZ")
                        time_max = (now + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
                        ev_resp  = requests.get(
                            f"{GOOGLE_CAL_BASE}/calendars/{runna_cal['id']}/events",
                            headers=headers,
                            params={
                                "timeMin":      time_min,
                                "timeMax":      time_max,
                                "singleEvents": "true",
                                "orderBy":      "startTime",
                                "maxResults":   30,
                            }
                        )
                        if ev_resp.status_code == 200:
                            for ev in ev_resp.json().get("items", []):
                                title = ev.get("summary", "")
                                start = ev.get("start", {})
                                ds    = start.get("date") or start.get("dateTime", "")[:10]
                                if title and ds:
                                    runna_by_date[ds] = {
                                        "title":    title,
                                        "day_type": classify_runna_event(title),
                                    }

        # ── Build 21-day plan (past 7 + today + future 13) ──────────────
        days = []
        for offset in range(-7, 14):
            d     = now + timedelta(days=offset)
            ds    = d.strftime("%Y-%m-%d")
            is_past   = offset < 0
            is_today  = offset == 0
            is_future = offset > 0

            # Determine day type and source
            if ds in run_by_date and (is_past or is_today):
                r            = run_by_date[ds]
                miles        = m_to_km(r["distance"])
                avg_hr       = r.get("average_heartrate")
                mov_time     = r.get("moving_time", 0)
                activity_type = r.get("type", "Run")
                from fuel import classify_activity
                day_type     = classify_activity(activity_type, miles, avg_hr, mov_time)
                source       = "strava"
                run_name     = r.get("name", "Activity")
                run_miles    = miles if activity_type in ("Run","VirtualRun","TrailRun") else 0.0
            elif ds in runna_by_date:
                # Planned workout from Runna calendar
                day_type  = runna_by_date[ds]["day_type"]
                source    = "runna"
                run_name  = runna_by_date[ds]["title"]
                run_miles = 0.0
            else:
                # No data — rest day
                day_type  = "rest"
                source    = "rest"
                run_name  = None
                run_miles = 0.0

            # ── Peloton recommendation for rest days ──────────────────
            peloton_rec      = None
            peloton_category = None
            if day_type == "rest" and source == "rest":
                try:
                    from peloton import recommend_workout

                    # Find most recent past run from already-built days list
                    prev_run_day = next(
                        (x for x in reversed(days) if x.get("day_type") not in ("rest", None)),
                        None
                    )
                    prev_type  = prev_run_day["day_type"] if prev_run_day else "rest"
                    # days_since = how many loop steps back the prev run was
                    days_since = (days[-1:] and len(days) - 1 - next(
                        (i for i, x in enumerate(days) if x is prev_run_day), len(days)
                    )) if prev_run_day else 99
                    days_since = max(1, days_since) if prev_run_day else 99

                    # Look ahead for next run in both runna calendar and run_by_date
                    next_run_type = "rest"
                    days_until    = 99
                    for look in range(1, 8):
                        future_ds = (d + timedelta(days=look)).strftime("%Y-%m-%d")
                        if future_ds in runna_by_date:
                            next_run_type = runna_by_date[future_ds]["day_type"]
                            days_until    = look
                            break
                        if future_ds in run_by_date:
                            r2 = run_by_date[future_ds]
                            from fuel import classify_activity
                            next_run_type = classify_activity(
                                r2.get("type","Run"), m_to_km(r2["distance"]),
                                r2.get("average_heartrate"), r2.get("moving_time",0)
                            )
                            days_until = look
                            break

                    peloton_rec = recommend_workout(
                        day_offset     = offset,
                        prev_run_type  = prev_type,
                        next_run_type  = next_run_type,
                        days_since_run = days_since,
                        days_until_run = days_until,
                    )
                    peloton_category = peloton_rec["category"] if peloton_rec else None
                except Exception:
                    pass

            day_plan = plan_day(ds, weight_kg, height_cm, age, day_type, source, run_name, run_miles,
                                peloton_category=peloton_category)
            day_plan["is_today"]      = is_today
            day_plan["is_past"]       = is_past
            day_plan["is_future"]     = is_future
            day_plan["dow"]           = d.strftime("%a")
            day_plan["display_date"]  = d.strftime("%b %d")
            day_plan["peloton"]       = peloton_rec
            days.append(day_plan)

        return jsonify({
            "days":             days,
            "weight_lbs":       weight_kg,
            "google_connected": google_connected,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route("/api/training/week")
def api_training_week():
    """
    Returns this week's complete training plan:
    - Run days from Strava + Runna calendar (from fuel plan)
    - Peloton workout recommendations for non-run days
    - Core add-ons included where appropriate
    """
    if not session.get("access_token"):
        return jsonify({"error": "not authenticated"}), 401
    try:
        from fuel import classify_day, classify_runna_event, plan_day, DAY_TYPE_COLOR, classify_activity, TRAINING_TYPES
        from peloton import build_weekly_plan, refresh_cache, get_cache_status

        weight_kg = float(_read_env("ATHLETE_WEIGHT_KG", "73"))
        height_cm = float(_read_env("ATHLETE_HEIGHT_CM", "180"))
        age = int(_read_env("ATHLETE_AGE", "27"))

        # ── Fetch Strava activities ──────────────────────────────────────
        runs = fetch_all_runs()
        now  = datetime.now()
        for r in runs:
            r["_dt"] = datetime.strptime(r["start_date_local"][:10], "%Y-%m-%d")

        run_by_date = {}
        for r in runs:
            ds = r["_dt"].strftime("%Y-%m-%d")
            if ds not in run_by_date or r["distance"] > run_by_date[ds]["distance"]:
                run_by_date[ds] = r

        # ── Fetch Runna calendar ─────────────────────────────────────────
        runna_by_date = {}
        google_connected = bool(session.get("google_access_token"))
        if google_connected:
            headers = get_google_headers()
            if headers:
                cal_resp = requests.get(
                    f"{GOOGLE_CAL_BASE}/users/me/calendarList", headers=headers
                )
                if cal_resp.status_code == 200:
                    calendars = cal_resp.json().get("items", [])
                    runna_cal = next(
                        (c for c in calendars if "runna" in c.get("summary", "").lower()), None
                    )
                    if runna_cal:
                        time_min = now.strftime("%Y-%m-%dT%H:%M:%SZ")
                        time_max = (now + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
                        ev_resp  = requests.get(
                            f"{GOOGLE_CAL_BASE}/calendars/{runna_cal['id']}/events",
                            headers=headers,
                            params={
                                "timeMin": time_min, "timeMax": time_max,
                                "singleEvents": "true", "orderBy": "startTime",
                                "maxResults": 30,
                            }
                        )
                        if ev_resp.status_code == 200:
                            for ev in ev_resp.json().get("items", []):
                                title = ev.get("summary", "")
                                start = ev.get("start", {})
                                ds    = start.get("date") or start.get("dateTime", "")[:10]
                                if title and ds:
                                    runna_by_date[ds] = {
                                        "title":    title,
                                        "day_type": classify_runna_event(title),
                                    }

        # ── Build 21-day fuel plan (reuse same logic) ────────────────────
        fuel_days = []
        for offset in range(-7, 14):
            d   = now + timedelta(days=offset)
            ds  = d.strftime("%Y-%m-%d")
            is_past   = offset < 0
            is_today  = offset == 0
            is_future = offset > 0

            if ds in run_by_date and (is_past or is_today):
                r             = run_by_date[ds]
                miles         = m_to_km(r["distance"])
                avg_hr        = r.get("average_heartrate")
                mov_time      = r.get("moving_time", 0)
                activity_type = r.get("type", "Run")
                day_type      = classify_activity(activity_type, miles, avg_hr, mov_time)
                source        = "strava"
                run_name      = r.get("name", "Activity")
                run_miles     = miles if activity_type in ("Run","VirtualRun","TrailRun") else 0.0
            elif ds in runna_by_date:
                day_type  = runna_by_date[ds]["day_type"]
                source    = "runna"
                run_name  = runna_by_date[ds]["title"]
                run_miles = 0.0
            else:
                day_type  = "rest"
                source    = "rest"
                run_name  = None
                run_miles = 0.0

            day_plan = plan_day(ds, weight_kg, height_cm, age, day_type, source, run_name, run_miles)
            day_plan["is_today"]      = is_today
            day_plan["is_past"]       = is_past
            day_plan["is_future"]     = is_future
            day_plan["dow"]           = d.strftime("%a")
            day_plan["display_date"]  = d.strftime("%b %d")
            fuel_days.append(day_plan)

        # ── Build weekly training plan with Peloton recommendations ──────
        weekly = build_weekly_plan(fuel_days)

        # ── Ensure cache is initialized ──────────────────────────────────
        status = get_cache_status()
        if not status.get("refreshed_at"):
            refresh_cache()
            status = get_cache_status()

        return jsonify({
            "week":             weekly,
            "google_connected": google_connected,
            "cache_status":     status,
            "weight_lbs":       weight_kg,
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/peloton/refresh", methods=["POST"])
def api_peloton_refresh():
    """Manually refresh the Peloton class cache."""
    if not session.get("access_token"):
        return jsonify({"error": "not authenticated"}), 401
    try:
        from peloton import refresh_cache
        status = refresh_cache()
        return jsonify({"ok": True, "status": status})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/fuel/weight", methods=["POST"])
def api_fuel_weight():
    """Update ATHLETE_WEIGHT_LBS in the .env file."""
    if not session.get("access_token"):
        return jsonify({"error": "not authenticated"}), 401
    try:
        data = request.get_json()
        weight = float(data.get("weight_lbs", 0))
        if weight < 100 or weight > 400:
            return jsonify({"error": "invalid weight"}), 400

        here = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(here, ".env")

        # Read existing .env
        try:
            with open(env_path) as f:
                lines = f.readlines()
        except FileNotFoundError:
            lines = []

        # Update or append ATHLETE_WEIGHT_KG
        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("ATHLETE_WEIGHT_KG="):
                new_lines.append(f"ATHLETE_WEIGHT_KG={weight}\n")
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.append(f"ATHLETE_WEIGHT_KG={weight}\n")

        with open(env_path, "w") as f:
            f.writelines(new_lines)

        return jsonify({"ok": True, "weight_lbs": weight})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/meals")
def api_meals():
    """Serve the meals database JSON."""
    if not session.get("access_token"):
        return jsonify({"error": "not authenticated"}), 401
    try:
        import json as _json
        meals_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meals.json")
        with open(meals_path) as f:
            return jsonify(_json.load(f))
    except FileNotFoundError:
        return jsonify({"error": "meals.json not found — add it to your Stride folder"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/debug/config")
def api_debug_config():
    cid = CLIENT_ID()
    csec = CLIENT_SECRET()
    return jsonify({
        "client_id_set":     bool(cid),
        "client_id_preview": cid[:4] + "..." if cid else "MISSING — .env not loaded",
        "secret_set":        bool(csec),
        "secret_preview":    csec[:4] + "..." if csec else "MISSING — .env not loaded",
        "redirect_uri":      REDIRECT_URI,
    })


@app.route("/api/performance")
def api_performance():
    if not session.get("access_token"): return jsonify({"error":"not authenticated"}), 401
    try:
        cache_key = f"perf_{session.get('access_token', '')[:16]}"
        cached = cache_get(cache_key)
        if cached:
            return jsonify(cached)
        runs = fetch_runs_only()
        if not runs: return jsonify({"error":"no runs found"}), 404
        now = datetime.now()
        for r in runs:
            r["_dt"] = datetime.strptime(r["start_date_local"][:10], "%Y-%m-%d")
        runs.sort(key=lambda r: r["_dt"])

        EST_MAX_HR = float(_read_env("ATHLETE_ESTIM_MAX_HR", "198"))

        # ── ATL/CTL (Acute/Chronic Training Load) ──────────────────────────────
        # TRIMP per run
        def trimp(r):
            hr = r.get("average_heartrate")
            t  = r.get("moving_time", 0)
            if not hr or not t: return m_to_km(r["distance"]) * 10  # fallback: ~10pts/mile
            ratio = hr / EST_MAX_HR
            return t / 60 * ratio * (0.64 * math.exp(1.92 * ratio))

        # Build daily load dict
        daily_load = defaultdict(float)
        for r in runs:
            daily_load[r["_dt"].date()] += trimp(r)

        # Compute ATL (7d) and CTL (42d) for last 16 weeks
        ctl_days, atl_days = [], []
        today = now.date()
        start = today - timedelta(weeks=16)
        day = start
        ctl = atl = 0.0
        k_ctl, k_atl = 1/42, 1/7
        while day <= today:
            load = daily_load.get(day, 0)
            ctl  = ctl  + k_ctl * (load - ctl)
            atl  = atl  + k_atl * (load - atl)
            ctl_days.append(round(ctl, 1))
            atl_days.append(round(atl, 1))
            day += timedelta(days=1)
        date_labels = [(start + timedelta(days=i)).strftime("%b %d") for i in range((today-start).days+1)]
        # Thin to ~80 points
        step = max(1, len(date_labels)//80)
        fitness_curve = {
            "labels": date_labels[::step],
            "ctl":    ctl_days[::step],
            "atl":    atl_days[::step],
            "tsb":    [round(c-a,1) for c,a in zip(ctl_days[::step], atl_days[::step])],
        }
        current_ctl = round(ctl, 1)
        current_atl = round(atl, 1)
        current_tsb = round(ctl - atl, 1)

        # ── Aerobic efficiency trend (pace per HR beat) ──────────────────────
        # Group by 4-week blocks, last 12 months
        eff_blocks = defaultdict(list)
        for r in runs:
            if r.get("average_heartrate") and r.get("average_speed",0)>0:
                age_weeks = (now - r["_dt"]).days // 7
                block = age_weeks // 4
                if block < 13:  # last ~12 months
                    pace_sec = 1000 / r["average_speed"]
                    eff = r["average_heartrate"] / (1000 / r["average_speed"] / 60)  # bpm per min/mile
                    eff_blocks[block].append((pace_sec, r["average_heartrate"], eff))
        eff_trend = []
        for block in sorted(eff_blocks.keys(), reverse=True):
            pts = eff_blocks[block]
            avg_pace = round(sum(p[0] for p in pts)/len(pts))
            avg_hr   = round(sum(p[1] for p in pts)/len(pts))
            # aerobic efficiency = speed / hr (higher = more efficient)
            avg_eff  = round(sum(p[2] for p in pts)/len(pts), 3)
            dt_approx = now - timedelta(weeks=block*4+2)
            eff_trend.append({
                "label": dt_approx.strftime("%b '%y"),
                "pace":  avg_pace,
                "pace_fmt": mps_to_pace(1000/avg_pace) if avg_pace>0 else "—",
                "hr":    avg_hr,
                "eff":   avg_eff,
            })

        # ── Rolling 6-week pace trend ─────────────────────────────────────────
        weekly_pace = []
        for i in range(11, -1, -1):
            wk_end   = now - timedelta(weeks=i)
            wk_start = wk_end - timedelta(weeks=6)
            bucket   = [r for r in runs if wk_start <= r["_dt"] <= wk_end
                        and r.get("average_speed",0)>0 and r.get("distance",0)>3000]
            if bucket:
                avg = sum(1000/r["average_speed"] for r in bucket) / len(bucket)
                weekly_pace.append({"label": wk_end.strftime("%b %d"), "pace_sec": round(avg),
                                    "pace_fmt": mps_to_pace(1000/avg*60/1000) if avg>0 else "—"})
        # fix pace fmt
        for wp in weekly_pace:
            s = wp["pace_sec"]
            wp["pace_fmt"] = f"{int(s//60)}:{int(s%60):02d}"

        # ── PR progression over time ──────────────────────────────────────────
        pr_prog = {"5k":[], "10k":[], "hm":[]}
        best = {"5k": None, "10k": None, "hm": None}
        for r in runs:
            d, t = r["distance"], r.get("moving_time", 0)
            if d >= 5000 and t > 0:
                pace = t/d
                if best["5k"] is None or pace < best["5k"]:
                    best["5k"] = pace
                    pr_prog["5k"].append({"date": r["_dt"].strftime("%b %d '%y"),
                                          "pace_sec": round(1000*pace), "pace_fmt": mps_to_pace(1/pace)})
            if d >= 10000 and t > 0:
                pace = t/d
                if best["10k"] is None or pace < best["10k"]:
                    best["10k"] = pace
                    pr_prog["10k"].append({"date": r["_dt"].strftime("%b %d '%y"),
                                           "pace_sec": round(1000*pace), "pace_fmt": mps_to_pace(1/pace)})
            if d >= 21097 and t > 0:
                pace = t/d
                if best["hm"] is None or pace < best["hm"]:
                    best["hm"] = pace
                    pr_prog["hm"].append({"date": r["_dt"].strftime("%b %d '%y"),
                                          "pace_sec": round(1000*pace), "pace_fmt": mps_to_pace(1/pace)})

        # ── Activity heatmap (last 52 weeks) ─────────────────────────────────
        run_date_set = defaultdict(float)
        for r in runs:
            run_date_set[r["_dt"].date()] += m_to_km(r["distance"])
        heatmap = []
        cal_start = today - timedelta(weeks=52)
        # align to Monday
        cal_start -= timedelta(days=cal_start.weekday())
        d = cal_start
        while d <= today:
            miles = run_date_set.get(d, 0)
            heatmap.append({
                "date": d.isoformat(),
                "miles": round(miles, 1),
                "level": 0 if miles==0 else 1 if miles<3 else 2 if miles<6 else 3 if miles<10 else 4,
            })
            d += timedelta(days=1)

        # ── Long run progression ──────────────────────────────────────────────
        long_runs = sorted(
            [r for r in runs if r["distance"] >= 12000],
            key=lambda r: r["_dt"]
        )[-20:]
        long_run_chart = {
            "labels": [r["_dt"].strftime("%b %d '%y") for r in long_runs],
            "miles":  [m_to_km(r["distance"]) for r in long_runs],
            "pace":   [round(1000/r["average_speed"]) if r.get("average_speed",0)>0 else None for r in long_runs],
        }

        # ── Summary stats for cards ───────────────────────────────────────────
        last8w = [r for r in runs if r["_dt"] >= now - timedelta(weeks=8)]
        prev8w = [r for r in runs if now - timedelta(weeks=16) <= r["_dt"] < now - timedelta(weeks=8)]

        def avg_pace_sec(rs):
            rs2 = [r for r in rs if r.get("average_speed",0)>0 and r.get("distance",0)>3000]
            if not rs2: return None
            return round(sum(1000/r["average_speed"] for r in rs2)/len(rs2))

        def avg_miles_pw(rs):
            if not rs: return 0
            weeks = max(1, len(set((r["_dt"] - timedelta(days=r["_dt"].weekday())).date() for r in rs)))
            return round(sum(m_to_km(r["distance"]) for r in rs)/weeks, 1)

        curr_pace = avg_pace_sec(last8w)
        prev_pace = avg_pace_sec(prev8w)
        pace_delta = None
        if curr_pace and prev_pace:
            pace_delta = prev_pace - curr_pace  # positive = got faster

        curr_mpw = avg_miles_pw(last8w)
        prev_mpw = avg_miles_pw(prev8w)

        result = {
            "fitness_curve":   fitness_curve,
            "current_ctl":     current_ctl,
            "current_atl":     current_atl,
            "current_tsb":     current_tsb,
            "eff_trend":       eff_trend,
            "weekly_pace":     weekly_pace,
            "pr_prog":         pr_prog,
            "heatmap":         heatmap,
            "long_run_chart":  long_run_chart,
            "summary": {
                "curr_pace":   curr_pace,
                "prev_pace":   prev_pace,
                "pace_delta":  pace_delta,
                "curr_mpw":    curr_mpw,
                "prev_mpw":    prev_mpw,
                "total_runs":  len(runs),
            }
        }
        cache_key = f"perf_{session.get('access_token', '')[:16]}"
        cache_set(cache_key, result)
        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/ollama/models")
def api_ollama_models():
    """Check whether an AI backend is available (Anthropic API key)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        # try reading from .env directly
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(here, ".env")) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ANTHROPIC_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    if key:
        return jsonify({"available": True, "models": ["claude-haiku-4-5-20251001"]})
    return jsonify({"available": False, "models": []})


@app.route("/api/insights")
def api_insights():
    """Use local Ollama to analyze the athlete's recent training."""
    if not session.get("access_token"): return jsonify({"error":"not authenticated"}), 401
    try:
        model = "claude-haiku-4-5-20251001"

        runs = fetch_all_runs()
        if not runs: return jsonify({"insights":"No run data found."}), 200
        now = datetime.now()
        for r in runs:
            r["_dt"] = datetime.strptime(r["start_date_local"][:10], "%Y-%m-%d")
        runs.sort(key=lambda r: r["_dt"])

        weeks = defaultdict(lambda: {"miles":0,"runs":0,"time":0,"hr_sum":0,"hr_n":0,"paces":[]})
        for r in runs:
            if r["_dt"] < now - timedelta(weeks=12): continue
            mon = (r["_dt"] - timedelta(days=r["_dt"].weekday())).strftime("%Y-%m-%d")
            weeks[mon]["miles"] += m_to_km(r["distance"])
            weeks[mon]["runs"]  += 1
            weeks[mon]["time"]  += r.get("moving_time", 0)
            if r.get("average_heartrate"):
                weeks[mon]["hr_sum"] += r["average_heartrate"]
                weeks[mon]["hr_n"]   += 1
            if r.get("average_speed",0) > 0 and r.get("distance",0) > 3000:
                weeks[mon]["paces"].append(round(1609.344/r["average_speed"]))

        wk_lines = []
        for wk, wd in sorted(weeks.items()):
            avg_hr   = round(wd["hr_sum"]/wd["hr_n"]) if wd["hr_n"] else None
            avg_pace = round(sum(wd["paces"])/len(wd["paces"])) if wd["paces"] else None
            pace_str = f"{int(avg_pace//60)}:{int(avg_pace%60):02d}/km" if avg_pace else "n/a"
            hr_str   = f"{avg_hr}bpm" if avg_hr else "n/a"
            wk_lines.append(f"  {wk}: {wd['runs']} runs, {round(wd['miles'],1)} km, avg pace {pace_str}, avg HR {hr_str}")

        athlete = session.get("athlete", {})
        name = athlete.get("firstname", "the athlete")

        prompt = f"""You are a knowledgeable running coach analyzing {name}'s training data from the last 12 weeks.

Weekly training summary (most recent last):
{chr(10).join(wk_lines)}

All-time total: {len(runs)} runs.

Please provide:
1. A 2-3 sentence overall assessment of recent training trends
2. 3-4 specific, actionable observations (e.g. about volume, consistency, pace, recovery)
3. 2-3 concrete recommendations for the next 4 weeks
4. One thing they are doing really well

Be specific, data-driven, and encouraging. Use actual numbers from the data. Keep total response under 400 words. Format with clear section headers using markdown bold (**Header**)."""

        # Get API key (env or .env file)
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            try:
                here = os.path.dirname(os.path.abspath(__file__))
                with open(os.path.join(here, ".env")) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("ANTHROPIC_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            break
            except Exception:
                pass

        if not api_key:
            return jsonify({"insights": "**No API key found.**\n\nAdd your Anthropic API key to `.env`:\n\n`ANTHROPIC_API_KEY=sk-ant-...`\n\nGet one free at console.anthropic.com — Claude Haiku costs ~$0.0003 per analysis (less than a penny).", "weeks_analyzed": 0})

        ai_resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model or "claude-haiku-4-5-20251001",
                "max_tokens": 700,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )

        if ai_resp.status_code == 200:
            text = ai_resp.json()["content"][0]["text"]
            return jsonify({"insights": text, "weeks_analyzed": len(weeks), "model": "Claude Haiku"})
        elif ai_resp.status_code == 401:
            return jsonify({"insights": "**Invalid API key.** Check that ANTHROPIC_API_KEY in your .env is correct.", "weeks_analyzed": 0})
        else:
            return jsonify({"insights": f"API error {ai_resp.status_code}: {ai_resp.text[:300]}", "weeks_analyzed": 0})

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

# ── Templates ─────────────────────────────────────────────────────────────────
LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stride</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#111217;--surface:#181a20;--border:#2a2d36;--orange:#f5a623;--text:#d4d8e2;--muted:#5a5f72}
body{background:var(--bg);color:var(--text);font-family:'JetBrains Mono',monospace;min-height:100vh;display:flex;align-items:center;justify-content:center}
.bg{position:fixed;inset:0;background-image:linear-gradient(var(--border) 1px,transparent 1px),linear-gradient(90deg,var(--border) 1px,transparent 1px);background-size:40px 40px;opacity:.35}
.card{position:relative;z-index:1;background:var(--surface);border:1px solid var(--border);border-radius:3px;padding:44px 36px;width:340px;text-align:center}
.logo{font-family:'Syne',sans-serif;font-size:2.2rem;font-weight:700;letter-spacing:.15em;color:var(--orange);margin-bottom:4px}
.sub{font-size:.68rem;color:var(--muted);letter-spacing:.08em;margin-bottom:32px}
.btn{display:flex;align-items:center;justify-content:center;gap:10px;background:#fc4c02;color:#fff;font-family:'Syne',sans-serif;font-size:.85rem;font-weight:700;padding:11px 22px;border-radius:2px;text-decoration:none;transition:opacity .15s}
.btn:hover{opacity:.85}
.note{margin-top:14px;font-size:.65rem;color:var(--muted);line-height:1.8}

</style></head><body>
<div class="bg"></div>
<div class="card">
  <div class="logo">STRIDE</div>
  <div class="sub">// running analytics · local dashboard</div>
  <a href="/login" class="btn">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169"/></svg>
    Connect with Strava
  </a>
  <p class="note">local only · no data stored · read-only access</p>
</div></body></html>"""

DASHBOARD_PAGE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stride — Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600&family=Syne:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#111217;--bg2:#0d0e12;--surface:#181a20;--surface2:#1e2028;
  --border:#252830;--border2:#2e3140;
  --orange:#f5a623;--orange2:#fc4c02;
  --green:#73bf69;--blue:#5794f2;--purple:#b877d9;--red:#f2495c;--yellow:#fade2a;
  --text:#d4d8e2;--muted:#5a5f72;--muted2:#8b90a0;
  --mono:'JetBrains Mono',monospace;--sans:'Syne',sans-serif;
  --drawer-w:680px;
}
html{font-size:13px}
body{background:var(--bg);color:var(--text);font-family:var(--mono);line-height:1.5;min-height:100vh;overflow-x:hidden}

/* topbar */
.topbar{display:flex;align-items:center;justify-content:space-between;background:var(--bg2);border-bottom:1px solid var(--border);padding:0 14px;height:38px;position:sticky;top:0;z-index:200}
.logo{font-family:var(--sans);font-size:.95rem;font-weight:700;letter-spacing:.12em;color:var(--orange)}
.bread{display:flex;align-items:center;gap:8px;font-size:.7rem;color:var(--muted);margin-left:12px}
.bread span{color:var(--muted2)}
.topbar-l{display:flex;align-items:center}
.topbar-r{display:flex;align-items:center;gap:10px}
.athl{font-size:.72rem;color:var(--muted2)}
.logout{font-size:.68rem;color:var(--muted);text-decoration:none;border:1px solid var(--border2);padding:2px 8px;border-radius:2px}
.logout:hover{color:var(--orange);border-color:var(--orange)}

/* tabs */
.tabs{display:flex;align-items:center;background:var(--bg2);border-bottom:1px solid var(--border);padding:0 14px;height:34px;gap:0;position:sticky;top:38px;z-index:190}
.tab{font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:0 14px;height:34px;display:flex;align-items:center;cursor:pointer;border-bottom:2px solid transparent;transition:color .15s,border-color .15s;white-space:nowrap}
.tab:hover{color:var(--text)}
.tab.active{color:var(--orange);border-bottom-color:var(--orange)}

/* page */
.tab-page{display:none;padding:10px 12px 60px}
.tab-page.active{display:block}
.tab-page.drawer-open{margin-right:var(--drawer-w)}
.row{display:grid;gap:6px;margin-bottom:6px}
.c5{grid-template-columns:repeat(5,1fr)}
.c4{grid-template-columns:repeat(4,1fr)}
.c3{grid-template-columns:1fr 1fr 1fr}
.c2{grid-template-columns:1fr 1fr}
.c31{grid-template-columns:3fr 1fr}
.cs2{grid-column:span 2}
.cs3{grid-column:span 3}

/* panels */
.panel{background:var(--surface);border:1px solid var(--border);border-radius:2px;overflow:hidden}
.ph{display:flex;align-items:center;justify-content:space-between;padding:5px 10px;border-bottom:1px solid var(--border);background:var(--bg2)}
.pt{font-size:.68rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--muted2)}
.ptag{font-size:.62rem;color:var(--muted)}
.pb{padding:8px 10px}

/* stat tiles */
.tile{padding:11px 13px}
.tlabel{font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:3px}
.tval{font-family:var(--sans);font-size:1.75rem;font-weight:700;line-height:1;margin-bottom:2px}
.tval.sm{font-size:1.2rem}
.tval.or{color:var(--orange)}.tval.gr{color:var(--green)}.tval.bl{color:var(--blue)}.tval.rd{color:var(--red)}.tval.pu{color:var(--purple)}
.tsub{font-size:.65rem;color:var(--muted)}
.tdelta{font-size:.68rem;margin-top:3px}
.tdelta.up{color:var(--green)}.tdelta.dn{color:var(--red)}.tdelta.neu{color:var(--muted)}

/* charts */
.cw{position:relative;width:100%}.h90{height:90px}.h110{height:110px}.h150{height:150px}.h180{height:180px}.h200{height:200px}.h220{height:220px}

/* tables */
.dt{width:100%;border-collapse:collapse;font-size:.73rem}
.dt th{font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:5px 10px;text-align:left;border-bottom:1px solid var(--border);background:var(--bg2);font-weight:500}
.dt td{padding:5px 10px;border-bottom:1px solid var(--border)}
.dt tr:last-child td{border-bottom:none}
.dt tr.clickable{cursor:pointer}
.dt tr.clickable:hover td{background:var(--surface2);color:var(--orange)}
.tn{color:var(--muted2);font-variant-numeric:tabular-nums}
.bk{display:inline-block;padding:1px 5px;border-radius:2px;font-size:.62rem;font-weight:600}
.bkg{background:rgba(115,191,105,.15);color:var(--green)}
.bkb{background:rgba(87,148,242,.15);color:var(--blue)}
.bko{background:rgba(245,166,35,.15);color:var(--orange)}
.bkr{background:rgba(242,73,92,.15);color:var(--red)}
.bkp{background:rgba(184,119,217,.15);color:var(--purple)}
.run-link{color:var(--text);cursor:pointer}
.run-link:hover{color:var(--orange)}

/* PRs */
.pr-grid{display:grid;grid-template-columns:repeat(4,1fr)}
.pr-item{padding:10px 12px;border-right:1px solid var(--border);cursor:pointer;transition:background .15s}
.pr-item:last-child{border-right:none}
.pr-item:hover{background:var(--surface2)}
.pr-type{font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:4px}
.pr-val{font-family:var(--sans);font-size:1.25rem;font-weight:700;color:var(--orange);line-height:1}
.pr-det{font-size:.63rem;color:var(--muted);margin-top:3px}

/* heatmap */
.heatmap-wrap{padding:8px 10px;overflow-x:auto}
.heatmap-grid{display:grid;grid-template-rows:repeat(7,10px);grid-auto-flow:column;gap:2px;width:max-content}
.hm-cell{width:10px;height:10px;border-radius:1px;cursor:default}
.hm-0{background:#1a1c22}
.hm-1{background:rgba(115,191,105,.3)}
.hm-2{background:rgba(115,191,105,.55)}
.hm-3{background:rgba(115,191,105,.8)}
.hm-4{background:#73bf69}
.hm-month-labels{display:flex;padding:0 10px 4px;gap:0;font-size:.6rem;color:var(--muted);overflow:hidden}

/* insights */
.insights-box{padding:14px 16px;font-size:.78rem;line-height:1.9;color:var(--text)}
.insights-box strong{color:var(--orange);font-weight:600}
.insights-loading{display:flex;align-items:center;gap:10px;padding:20px;color:var(--muted);font-size:.75rem}
.insight-btn{background:var(--surface2);border:1px solid var(--border2);color:var(--muted2);font-family:var(--mono);font-size:.7rem;padding:5px 14px;cursor:pointer;border-radius:2px;transition:all .15s}
.insight-btn:hover{color:var(--orange);border-color:var(--orange)}
.insight-btn:disabled{opacity:.4;cursor:default}

/* fitness status badge */
.status-badge{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:2px;font-size:.68rem;font-weight:600;margin-bottom:8px}

/* drawer */
.drawer{position:fixed;top:0;right:0;bottom:0;width:var(--drawer-w);background:var(--surface);border-left:1px solid var(--border2);z-index:300;overflow-y:auto;transform:translateX(100%);transition:transform .3s ease}
.drawer.open{transform:translateX(0)}
.drawer-topbar{display:flex;align-items:center;justify-content:space-between;padding:0 14px;height:38px;background:var(--bg2);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10}
.drawer-title{font-family:var(--sans);font-size:.85rem;font-weight:700;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:460px}
.drawer-close{background:none;border:1px solid var(--border2);color:var(--muted);font-family:var(--mono);font-size:.7rem;padding:3px 10px;cursor:pointer;border-radius:2px}
.drawer-close:hover{color:var(--orange);border-color:var(--orange)}
.drawer-body{padding:12px}
#runMap{height:260px;width:100%;background:var(--bg2);border-radius:2px;margin-bottom:10px}
.leaflet-container{background:#1a1c22}
.meta-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px}
.meta-cell{background:var(--bg2);border:1px solid var(--border);border-radius:2px;padding:8px 10px}
.meta-label{font-size:.6rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:2px}
.meta-val{font-family:var(--sans);font-size:1.1rem;font-weight:700;color:var(--text)}
.meta-val.or{color:var(--orange)}.meta-val.gr{color:var(--green)}.meta-val.bl{color:var(--blue)}.meta-val.rd{color:var(--red)}
.training-block{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:10px}
.t-cell{background:var(--bg2);border:1px solid var(--border);padding:8px 10px;border-radius:2px}
.t-label{font-size:.6rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:3px}
.t-val{font-family:var(--sans);font-size:1.4rem;font-weight:700;color:var(--orange)}
.t-sub{font-size:.62rem;color:var(--muted);margin-top:2px}
.zone-bar{display:flex;gap:2px;height:8px;border-radius:2px;overflow:hidden;margin-top:6px}
.zs{height:100%}
.stream-charts{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}
.sc-panel{background:var(--bg2);border:1px solid var(--border);border-radius:2px;padding:8px}
.sc-title{font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px}
.sc-wrap{position:relative;height:100px}
.splits-panel{background:var(--bg2);border:1px solid var(--border);border-radius:2px;margin-bottom:10px;overflow:hidden}
.strava-link{display:inline-flex;align-items:center;gap:6px;background:#fc4c02;color:#fff;font-family:var(--sans);font-size:.75rem;font-weight:700;padding:6px 14px;border-radius:2px;text-decoration:none;margin-top:4px}
.strava-link:hover{opacity:.85}

/* loading */
.loading{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:80vh;gap:12px}
.perf-loading{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:60vh;gap:12px}
.spin{width:28px;height:28px;border:2px solid var(--border2);border-top-color:var(--orange);border-radius:50%;animation:sp .7s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.lmsg{font-size:.72rem;color:var(--muted)}
.drawer-loading{display:flex;flex-direction:column;align-items:center;justify-content:center;height:300px;gap:12px}
/* ── Info tab ── */
.info-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px}
.info-card{background:var(--surface);border:1px solid var(--border);border-radius:2px;padding:14px 16px}
.info-card-title{font-family:var(--sans);font-size:.85rem;font-weight:700;color:var(--orange);margin-bottom:6px}
.info-card-sub{font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:8px}
.info-card p{font-size:.75rem;color:var(--muted2);line-height:1.8;margin-bottom:6px}
.info-card p:last-child{margin-bottom:0}
.info-tag{display:inline-block;padding:1px 7px;border-radius:2px;font-size:.62rem;font-weight:600;margin-right:4px;margin-bottom:4px}
.info-formula{background:var(--bg2);border:1px solid var(--border);border-radius:2px;padding:6px 10px;font-size:.68rem;color:var(--green);margin:6px 0;font-family:var(--mono)}
.info-section-head{font-family:var(--sans);font-size:1rem;font-weight:700;color:var(--text);margin:18px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border)}
.info-section-head:first-child{margin-top:0}

/* ── Mobile responsive ── */
@media(max-width:768px){
  :root{--drawer-w:100vw}
  html{font-size:12px}

  .bread{display:none}
  .topbar-r .athl{display:none}
  .logout{font-size:.65rem;padding:2px 6px}

  .tabs{gap:0;padding:0 8px;overflow-x:auto}
  .tab{font-size:.65rem;padding:0 10px;white-space:nowrap}

  .tab-page{padding:8px 8px 60px}

  .row.c5,.row.c4{grid-template-columns:1fr 1fr}
  .row.c3,.row.c2,.row.c31{grid-template-columns:1fr}
  .cs2,.cs3{grid-column:span 1}

  .info-grid{grid-template-columns:1fr}

  .pr-grid{grid-template-columns:1fr 1fr}
  .pr-item:nth-child(2n){border-right:none}
  .pr-item:nth-child(n+3){border-top:1px solid var(--border)}

  .meta-grid{grid-template-columns:1fr 1fr}
  .training-block{grid-template-columns:1fr}
  .stream-charts{grid-template-columns:1fr}

  .dt th,.dt td{padding:4px 8px;font-size:.68rem}
  .dt th:nth-child(n+5),.dt td:nth-child(n+5){display:none}

  .panel{border-radius:2px}
  .tile{padding:10px 12px}
  .tval{font-size:1.4rem}

  .h110,.h150,.h180,.h200,.h220{height:140px}

  .heatmap-wrap{padding:6px 4px}
  .hm-cell{width:9px;height:9px}
  .heatmap-grid{gap:1px}

  .drawer{top:38px}
  .drawer-topbar{height:38px}
  #runMap{height:200px}
}

@media(max-width:480px){
  .row.c5,.row.c4{grid-template-columns:1fr 1fr}
  .topbar{padding:0 10px}
  .logo{font-size:.85rem}
}

#dash-tab{display:none}

.fuel-strip{display:flex;flex-wrap:nowrap;gap:4px;min-width:max-content}
.fuel-cell{min-width:62px;background:var(--bg2);border:1px solid var(--border);border-radius:2px;padding:7px 5px;text-align:center;cursor:pointer;transition:border-color .15s,background .15s;flex-shrink:0}
.fuel-cell:hover{border-color:var(--border2);background:var(--surface2)}
.fuel-cell-active{border-color:var(--orange) !important;background:var(--surface2) !important}
.fuel-cell-today{border-color:var(--border2)}
.fuel-cell-future{opacity:.85}
.fuel-cell-dow{font-size:.6rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:2px}
.fuel-cell-date{font-size:.62rem;color:var(--muted2);margin-bottom:5px}
.fuel-cell-dot{width:8px;height:8px;border-radius:50%;margin:0 auto 3px}
.fuel-cell-type{font-size:.58rem;text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px}
.fuel-cell-cal{font-size:.65rem;color:var(--muted)}
.fuel-cell-pelo{font-size:.55rem;color:var(--purple);letter-spacing:.03em;margin-bottom:1px}
.fuel-detail-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.fuel-macro-row{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:8px}
.fuel-macro-cell{background:var(--bg2);border:1px solid var(--border);border-radius:2px;padding:7px 8px}
.fuel-macro-label{font-size:.6rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:2px}
.fuel-macro-val{font-family:var(--sans);font-size:1.1rem;font-weight:700;line-height:1}
.fuel-macro-sub{font-size:.6rem;color:var(--muted);margin-top:2px}
.fuel-timing-grid{display:grid;grid-template-columns:1fr;gap:6px;margin-bottom:8px}
.fuel-timing-cell{background:var(--bg2);border:1px solid var(--border);border-radius:2px;padding:8px 10px}
.fuel-timing-label{font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;color:var(--orange);font-weight:600;margin-bottom:3px}
.fuel-timing-text{font-size:.72rem;color:var(--muted2);line-height:1.7}

.train-week{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;margin-bottom:16px}
@media(max-width:900px){.train-week{grid-template-columns:repeat(4,1fr)}}
@media(max-width:500px){.train-week{grid-template-columns:repeat(2,1fr)}}
.train-day{background:var(--surface);border:1px solid var(--border);border-radius:3px;overflow:hidden;transition:border-color .15s}
.train-day:hover{border-color:var(--border2)}
.train-day.today{border-color:var(--border2)}
.train-day-header{padding:7px 9px 5px;border-bottom:1px solid var(--border);background:var(--surface2)}
.train-day-dow{font-family:var(--mono);font-size:.58rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.train-day-date{font-size:.7rem;color:var(--muted2)}
.train-day-body{padding:7px 9px 8px}
.train-run-badge{display:inline-block;font-family:var(--mono);font-size:.58rem;text-transform:uppercase;letter-spacing:.06em;padding:2px 6px;border-radius:2px;margin-bottom:5px}
.train-run-name{font-size:.72rem;font-weight:600;color:var(--text);margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.train-run-meta{font-family:var(--mono);font-size:.62rem;color:var(--muted);margin-bottom:6px}
.train-pelo-divider{border:none;border-top:1px dashed var(--border);margin:6px 0}
.train-pelo-label{font-family:var(--mono);font-size:.55rem;text-transform:uppercase;letter-spacing:.1em;color:var(--purple);margin-bottom:3px}
.train-pelo-title{font-size:.7rem;color:var(--text);margin-bottom:1px;line-height:1.4}
.train-pelo-meta{font-family:var(--mono);font-size:.6rem;color:var(--muted);margin-bottom:4px}
.train-pelo-reason{font-size:.62rem;color:var(--muted2);line-height:1.5;font-style:italic;margin-bottom:5px}
.train-pelo-link{display:inline-block;font-family:var(--mono);font-size:.6rem;color:var(--purple);text-decoration:none;border:1px solid rgba(168,85,247,.3);padding:2px 7px;border-radius:2px;background:rgba(168,85,247,.07)}
.train-pelo-link:hover{background:rgba(168,85,247,.15);border-color:rgba(168,85,247,.5)}
.train-core-addon{margin-top:5px;padding:5px 7px;background:rgba(87,148,242,.07);border:1px solid rgba(87,148,242,.2);border-radius:2px}
.train-core-label{font-family:var(--mono);font-size:.55rem;text-transform:uppercase;letter-spacing:.1em;color:var(--blue);margin-bottom:2px}
.train-core-title{font-size:.65rem;color:var(--muted2)}
.train-rest-label{font-size:.68rem;color:var(--muted);text-align:center;padding:10px 0}
.train-cache-bar{display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--surface);border:1px solid var(--border);border-radius:3px;margin-bottom:12px;font-size:.68rem;color:var(--muted)}

@media(max-width:600px){
  .fuel-macro-row{grid-template-columns:repeat(2,1fr)}
  .fuel-timing-grid{grid-template-columns:1fr}
  .fuel-detail-header{flex-direction:column;gap:6px}
  .fuel-detail-header > div:last-child{text-align:left}
}
@media(max-width:600px){
  .train-cache-bar{flex-wrap:wrap;gap:6px}
  .train-day{min-width:130px}
}
.meals-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.meals-select{background:var(--surface2);border:1px solid var(--border2);color:var(--text);font-family:var(--mono);font-size:.68rem;padding:4px 8px;border-radius:2px;cursor:pointer}
.meals-select:focus{outline:none;border-color:var(--orange)}
.meals-day-tabs{display:flex;gap:4px;overflow-x:auto;margin-bottom:12px;padding-bottom:2px;-webkit-overflow-scrolling:touch}
.meals-day-tab{font-family:var(--mono);font-size:.62rem;text-transform:uppercase;letter-spacing:.06em;padding:5px 12px;border-radius:2px;border:1px solid var(--border);background:var(--surface);color:var(--muted);cursor:pointer;white-space:nowrap;flex-shrink:0;transition:all .15s}
.meals-day-tab:hover{border-color:var(--border2);color:var(--muted2)}
.meals-day-tab.active{background:var(--orange);border-color:var(--orange);color:#fff}
.meals-day-tab .dot{width:6px;height:6px;border-radius:50%;display:inline-block;margin-right:4px;vertical-align:middle}
.meal-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:680px){.meal-grid{grid-template-columns:1fr}}
.meal-card-s{background:var(--surface);border:1px solid var(--border);border-radius:3px;overflow:hidden;transition:border-color .15s;cursor:pointer}
.meal-card-s:hover{border-color:var(--border2)}
.meal-card-s.expanded{border-color:var(--orange)}
.meal-card-header{display:flex;justify-content:space-between;align-items:center;padding:7px 11px;background:var(--surface2);border-bottom:1px solid var(--border)}
.meal-card-label{font-family:var(--mono);font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
.meal-card-macros{display:flex;gap:6px;font-family:var(--mono);font-size:.6rem}
.meal-card-body{padding:10px 12px}
.meal-card-name{font-family:var(--sans);font-size:.92rem;font-weight:700;margin-bottom:3px;color:var(--text)}
.meal-card-desc{font-size:.7rem;color:var(--muted2);line-height:1.7;margin-bottom:6px}
.meal-card-tags{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px}
.meal-tag{font-family:var(--mono);font-size:.56rem;padding:2px 5px;border-radius:2px;border:1px solid var(--border2);color:var(--muted)}
.meal-expand{background:var(--bg2);border:1px solid var(--border);border-radius:2px;padding:8px 10px;margin-top:6px}
.meal-expand-title{font-family:var(--mono);font-size:.58rem;text-transform:uppercase;letter-spacing:.08em;color:var(--orange);margin-bottom:5px}
.meal-expand ul{padding-left:14px;font-size:.68rem;color:var(--muted2);line-height:1.9}
.meal-expand ol{padding-left:14px;font-size:.68rem;color:var(--muted2);line-height:1.9}
.meals-day-summary{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;padding:8px 12px;background:var(--surface);border:1px solid var(--border);border-radius:3px;font-family:var(--mono);font-size:.65rem}
.mds-item{display:flex;flex-direction:column;align-items:center}
.mds-val{font-size:.9rem;font-weight:600;font-family:var(--sans)}
.mds-label{font-size:.55rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-top:1px}
</style></head><body>

<div class="topbar">
  <div class="topbar-l">
    <div class="logo">STRIDE</div>
    <div class="bread"><span>Dashboards</span> / <span id="tabBread">Overview</span></div>
  </div>
  <div class="topbar-r">
    <span class="athl" id="topAthl"></span>
    <button class="logout" onclick="refreshData()" id="refreshBtn">↺ refresh</button>
    <a href="/logout" class="logout">sign out</a>
  </div>
</div>

<div class="tabs">
  <div class="tab active" data-tab="overview" onclick="switchTab('overview')">Overview</div>
  <div class="tab" data-tab="performance" onclick="switchTab('performance')">Performance</div>
  <div class="tab" data-tab="info" onclick="switchTab('info')">Guide</div>
  <div class="tab" data-tab="fuel" onclick="switchTab('fuel')">Fuel</div>
  <div class="tab" data-tab="train" onclick="switchTab('train')">Train</div>
  <div class="tab" data-tab="meals" onclick="switchTab('meals')">Meals</div>
</div>

<div class="loading" id="loading">
  <div class="spin"></div>
  <div class="lmsg">fetching your runs from strava...</div>
</div>

<div id="dash-tab">

<!-- ══════════════════════════ OVERVIEW TAB ══════════════════════════ -->
<div class="tab-page active" id="tab-overview">

  <div class="row c5">
    <div class="panel"><div class="tile"><div class="tlabel">This Week</div><div class="tval bl" id="s-wk-mi">—</div><div class="tsub" id="s-wk-sub">—</div></div></div>
    <div class="panel"><div class="tile"><div class="tlabel">This Month</div><div class="tval gr" id="s-mo-mi">—</div><div class="tsub" id="s-mo-sub">—</div></div></div>
    <div class="panel"><div class="tile"><div class="tlabel">This Year</div><div class="tval or" id="s-yr-mi">—</div><div class="tsub" id="s-yr-sub">—</div></div></div>
    <div class="panel"><div class="tile"><div class="tlabel">All-Time Km</div><div class="tval" id="s-at-mi">—</div><div class="tsub" id="s-at-sub">—</div></div></div>
    <div class="panel"><div class="tile"><div class="tlabel">Run Streak</div><div class="tval or" id="s-str">—</div><div class="tsub" id="s-str-sub">—</div></div></div>
  </div>

  <div class="row c2">
    <div class="panel">
      <div class="ph"><span class="pt">Weekly Km</span><span class="ptag">last 20 weeks</span></div>
      <div class="pb"><div class="cw h110"><canvas id="wkChart"></canvas></div></div>
    </div>
    <div class="panel">
      <div class="ph"><span class="pt">Monthly Km</span><span class="ptag">last 12 months</span></div>
      <div class="pb"><div class="cw h110"><canvas id="moChart"></canvas></div></div>
    </div>
  </div>

  <div class="row c3">
    <div class="panel cs2">
      <div class="ph"><span class="pt">Avg Pace Trend</span><span class="ptag">last 30 runs · click point to open run</span></div>
      <div class="pb"><div class="cw h110"><canvas id="paceChart"></canvas></div></div>
    </div>
    <div class="panel">
      <div class="ph"><span class="pt">Distance Mix</span><span class="ptag">all runs</span></div>
      <div class="pb"><div class="cw h110"><canvas id="distChart"></canvas></div></div>
    </div>
  </div>

  <div class="panel" style="margin-bottom:6px">
    <div class="ph"><span class="pt">Personal Records</span><span class="ptag">click to open run</span></div>
    <div class="pr-grid" id="prGrid"></div>
  </div>

  <div class="row c2">
    <div class="panel">
      <div class="ph"><span class="pt">Week at a Glance</span><span class="ptag">last 8 weeks</span></div>
      <table class="dt"><thead><tr><th>Week of</th><th>Runs</th><th>Km</th><th>Avg Pace</th><th>Time</th><th>Elev ↑</th></tr></thead>
      <tbody id="wkBody"></tbody></table>
    </div>
    <div class="panel">
      <div class="ph"><span class="pt">Recent Activities</span><span class="ptag">click row to inspect run</span></div>
      <table class="dt"><thead><tr><th>Run</th><th>Date</th><th>Km</th><th>Pace</th><th>Time</th><th>HR</th><th>Elev ↑</th></tr></thead>
      <tbody id="rcBody"></tbody></table>
    </div>
  </div>

</div><!-- /overview -->

<!-- ══════════════════════════ PERFORMANCE TAB ══════════════════════════ -->
<div class="tab-page" id="tab-performance">

  <div class="perf-loading" id="perfLoading">
    <div class="spin"></div>
    <div class="lmsg">computing training metrics...</div>
  </div>

  <div id="perfContent" style="display:none">

    <!-- Status cards -->
    <div class="row c4" style="margin-bottom:6px">
      <div class="panel"><div class="tile">
        <div class="tlabel">Fitness (CTL)</div>
        <div class="tval bl" id="p-ctl">—</div>
        <div class="tsub">chronic training load</div>
        <div class="tdelta" id="p-ctl-sub">—</div>
      </div></div>
      <div class="panel"><div class="tile">
        <div class="tlabel">Fatigue (ATL)</div>
        <div class="tval or" id="p-atl">—</div>
        <div class="tsub">acute training load</div>
        <div class="tdelta" id="p-atl-sub">—</div>
      </div></div>
      <div class="panel"><div class="tile">
        <div class="tlabel">Form (TSB)</div>
        <div class="tval" id="p-tsb">—</div>
        <div class="tsub">fitness − fatigue</div>
        <div class="tdelta" id="p-tsb-sub">—</div>
      </div></div>
      <div class="panel"><div class="tile">
        <div class="tlabel">Avg Pace (8wk vs prior)</div>
        <div class="tval sm" id="p-pace">—</div>
        <div class="tsub" id="p-pace-sub">—</div>
        <div class="tdelta" id="p-pace-delta">—</div>
      </div></div>
    </div>

    <!-- CTL/ATL curve -->
    <div class="row c2">
      <div class="panel cs2">
        <div class="ph"><span class="pt">Fitness / Fatigue / Form</span><span class="ptag">16 weeks · CTL=blue ATL=orange TSB=green</span></div>
        <div class="pb"><div class="cw h180"><canvas id="fitChart"></canvas></div></div>
      </div>
    </div>

    <!-- Pace trend + aerobic efficiency -->
    <div class="row c2">
      <div class="panel">
        <div class="ph"><span class="pt">6-Week Rolling Avg Pace</span><span class="ptag">lower = faster · last 12 weeks</span></div>
        <div class="pb"><div class="cw h150"><canvas id="rollingPaceChart"></canvas></div></div>
      </div>
      <div class="panel">
        <div class="ph"><span class="pt">Aerobic Efficiency</span><span class="ptag">HR per min/km · higher = more efficient · 4-week blocks</span></div>
        <div class="pb"><div class="cw h150"><canvas id="effChart"></canvas></div></div>
      </div>
    </div>

    <!-- PR progression + long run chart -->
    <div class="row c2">
      <div class="panel">
        <div class="ph">
          <span class="pt">PR Progression</span>
          <div style="display:flex;gap:4px">
            <button class="insight-btn" id="pr5kBtn" onclick="showPR('5k')" style="color:var(--orange);border-color:var(--orange)">5K</button>
            <button class="insight-btn" id="pr10kBtn" onclick="showPR('10k')">10K</button>
            <button class="insight-btn" id="prHmBtn" onclick="showPR('hm')">Half</button>
          </div>
        </div>
        <div class="pb"><div class="cw h150"><canvas id="prProgChart"></canvas></div></div>
      </div>
      <div class="panel">
        <div class="ph"><span class="pt">Long Run Progression</span><span class="ptag">runs ≥ 7.5 mi · last 20</span></div>
        <div class="pb"><div class="cw h150"><canvas id="longRunChart"></canvas></div></div>
      </div>
    </div>

    <!-- Activity heatmap -->
    <div class="panel" style="margin-bottom:6px">
      <div class="ph"><span class="pt">Activity Heatmap</span><span class="ptag">last 52 weeks · darker = more miles</span></div>
      <div class="hm-month-labels" id="hmMonthLabels"></div>
      <div class="heatmap-wrap"><div class="heatmap-grid" id="heatmapGrid"></div></div>
      <div style="display:flex;align-items:center;gap:6px;padding:6px 10px;font-size:.62rem;color:var(--muted)">
        Less <div class="hm-cell hm-0" style="display:inline-block"></div>
        <div class="hm-cell hm-1" style="display:inline-block"></div>
        <div class="hm-cell hm-2" style="display:inline-block"></div>
        <div class="hm-cell hm-3" style="display:inline-block"></div>
        <div class="hm-cell hm-4" style="display:inline-block"></div> More
      </div>
    </div>

    <!-- AI Insights -->
    <div class="panel" style="margin-bottom:6px">
      <div class="ph">
        <span class="pt">AI Coach Insights</span>
        <button class="insight-btn" id="insightBtn" onclick="loadInsights()">✦ Generate insights</button>
      </div>
      <div id="insightsBody">
        <div style="padding:14px 16px;font-size:.72rem;color:var(--muted)">
          Click "Generate insights" for an AI analysis of your last 12 weeks of training.<br>
          <span style="font-size:.65rem;opacity:.7">Requires ANTHROPIC_API_KEY in your .env file. Free to add — get one at console.anthropic.com</span>
        </div>
      </div>
    </div>

  </div><!-- /perfContent -->
</div><!-- /performance tab -->

<!-- ══════════════════════════ GUIDE TAB ══════════════════════════ -->
<div class="tab-page" id="tab-info">
<div style="max-width:900px;margin:0 auto;padding:4px 0 40px">

  <div class="info-section-head">Training Load Metrics</div>
  <div class="info-grid">
    <div class="info-card">
      <div class="info-card-title">CTL — Fitness</div>
      <div class="info-card-sub">Chronic Training Load · 42-day average</div>
      <p>Your long-term fitness level. Built slowly over weeks and months. A rising CTL means you are getting fitter. A typical recreational runner sits between 30–60; competitive runners often exceed 80–100.</p>
      <p>It takes roughly 6–10 weeks of consistent training to meaningfully raise your CTL. You cannot shortcut this.</p>
      <div class="info-formula">CTL = previous CTL + (1/42) × (today's load − CTL)</div>
    </div>
    <div class="info-card">
      <div class="info-card-title">ATL — Fatigue</div>
      <div class="info-card-sub">Acute Training Load · 7-day average</div>
      <p>How tired you are right now. Spikes quickly after a hard week and drops fast when you rest. ATL will always be more volatile than CTL.</p>
      <p>A high ATL relative to your CTL means you have been training harder than your body is used to — which is fine in a training block but not sustainable indefinitely.</p>
      <div class="info-formula">ATL = previous ATL + (1/7) × (today's load − ATL)</div>
    </div>
    <div class="info-card">
      <div class="info-card-title">TSB — Form</div>
      <div class="info-card-sub">Training Stress Balance · CTL minus ATL</div>
      <p>The most actionable number in the model. Positive means fresh, negative means fatigued.</p>
      <p><span class="info-tag bkg">+5 to +15</span> Peak race readiness<br>
         <span class="info-tag bkb">-5 to +5</span> Normal training<br>
         <span class="info-tag bko">-10 to -20</span> Hard training block<br>
         <span class="info-tag bkr">below -25</span> Overreaching — rest</p>
      <div class="info-formula">TSB = CTL − ATL</div>
    </div>
    <div class="info-card">
      <div class="info-card-title">TRIMP Score</div>
      <div class="info-card-sub">Training Impulse · per run</div>
      <p>A single number representing the training load of one run. Accounts for both duration and intensity via heart rate. A 30-minute easy run might score 20; a hard 10-km tempo might score 80+.</p>
      <p>Used to calculate ATL and CTL. If you ran without HR data, distance is used as a proxy.</p>
      <div class="info-formula">TRIMP = time × HR_ratio × e^(1.92 × HR_ratio)</div>
    </div>
    <div class="info-card">
      <div class="info-card-title">Suffer Score</div>
      <div class="info-card-sub">Strava Relative Effort</div>
      <p>Strava's own version of training load. Uses your HR data to estimate how hard a workout was relative to your personal HR zones. Reported directly from Strava — only available if you ran with a HR monitor.</p>
      <p>Useful for comparing efforts within your own history, but not standardized across athletes.</p>
    </div>
    <div class="info-card">
      <div class="info-card-title">Aerobic Efficiency</div>
      <div class="info-card-sub">HR per min/km · 4-week blocks</div>
      <p>Measures how much heart rate it costs you per unit of pace. A higher value means you are running the same pace at a lower HR — the clearest sign of aerobic improvement.</p>
      <p>Efficiency naturally improves with consistent easy running over months. Heat, altitude, illness, and fatigue all depress it temporarily.</p>
    </div>
  </div>

  <div class="info-section-head">Pace & Effort</div>
  <div class="info-grid">
    <div class="info-card">
      <div class="info-card-title">Average Pace</div>
      <div class="info-card-sub">min:seg per km</div>
      <p>Total moving time divided by distance. Shown throughout the dashboard as mm:ss per km. Note that Strava uses moving time (excluding stopped time), so GPS pauses at lights do not inflate your pace.</p>
      <p>The 6-week rolling average on the Performance tab smooths out outliers and shows your true trend.</p>
    </div>
    <div class="info-card">
      <div class="info-card-title">Intensity Zones</div>
      <div class="info-card-sub">Based on % of max HR (est. 198 bpm)</div>
      <p><span class="info-tag bkb">Easy Z1/Z2</span> below 70% — conversational pace, builds aerobic base<br>
         <span class="info-tag bkg">Tempo Z3</span> 70–80% — comfortably hard, lactate threshold<br>
         <span class="info-tag bko">Threshold Z4</span> 80–90% — race effort, 10K to half marathon pace<br>
         <span class="info-tag bkr">Max Z5</span> above 90% — interval/sprint effort</p>
      <p>The widely recommended distribution is 80% of km in Z1/Z2 and 20% in Z3+. Most runners do the opposite and wonder why they plateau.</p>
    </div>
    <div class="info-card">
      <div class="info-card-title">Cadence</div>
      <div class="info-card-sub">Steps per minute (both feet)</div>
      <p>The number of foot strikes per minute. A higher cadence generally means shorter ground contact time and less impact stress on joints. The oft-cited target of 180 spm is a rough guideline, not a rule.</p>
      <p>Most runners improve efficiency by increasing their natural cadence by 5–10%. Shown in the run detail drawer if your watch records it.</p>
    </div>
  </div>

  <div class="info-section-head">Charts Explained</div>
  <div class="info-grid">
    <div class="info-card">
      <div class="info-card-title">Fitness / Fatigue / Form</div>
      <div class="info-card-sub">Performance tab · 16-week view</div>
      <p>The classic CTL/ATL/TSB chart used by coaches. Blue rising = building fitness. Orange spiking = accumulated fatigue from a hard block. Green climbing positive = freshening up for a race.</p>
      <p>The ideal taper pattern: CTL at its peak, ATL dropping for 1–2 weeks, TSB climbing from negative toward +5 to +10 on race day.</p>
    </div>
    <div class="info-card">
      <div class="info-card-title">PR Progression</div>
      <div class="info-card-sub">Performance tab · 5K / 10K / Half</div>
      <p>Each point is a new personal best at that distance — not just your fastest run of that distance, but each time you set a new PR. A staircase pattern going down over time means you are improving.</p>
      <p>Gaps in the chart are periods where you did not set a new PR, which is completely normal — PRs come in clusters after training blocks.</p>
    </div>
    <div class="info-card">
      <div class="info-card-title">Pace / HR / Elevation Streams</div>
      <div class="info-card-sub">Run detail drawer · over distance</div>
      <p>Second-by-second data from your GPS watch, plotted over distance rather than time. The pace chart Y-axis is inverted (lower = faster). Spikes in the HR chart after hills show your cardiac response to elevation.</p>
      <p>Comparing HR and pace on the same run tells you how hard you actually worked versus how fast you went — the gap between the two is your fitness.</p>
    </div>
  </div>

  <div class="info-section-head">Tips</div>
  <div class="info-grid">
    <div class="info-card">
      <div class="info-card-title">How to improve CTL safely</div>
      <div class="info-card-sub">The 10% rule and beyond</div>
      <p>Do not increase weekly kilometers by more than 10% per week. More importantly, follow every 3 weeks of building with 1 recovery week at 60–70% of your peak kilometers. This is when fitness actually consolidates.</p>
      <p>Watch your TSB — if it stays below −20 for more than 2 weeks in a row, take an easy week regardless of your plan.</p>
    </div>
    <div class="info-card">
      <div class="info-card-title">Refreshing your data</div>
      <div class="info-card-sub">Cache · 15-minute TTL</div>
      <p>The dashboard caches your Strava data for 15 minutes to avoid slow load times. After a run, click the <strong>↺ refresh</strong> button in the top right to force a fresh fetch and see your latest activity.</p>
      <p>The cache resets automatically when the server restarts. Run detail data (maps, streams) is always fetched live when you click a run.</p>
    </div>
    <div class="info-card">
      <div class="info-card-title">HR data quality</div>
      <div class="info-card-sub">Optical vs chest strap</div>
      <p>Many of the training load calculations rely on accurate heart rate data. Optical wrist sensors are convenient but can be unreliable at high intensities or in cold weather. Chest straps give cleaner data.</p>
      <p>Runs without HR data fall back to distance-based load estimates, which are less accurate but still useful for tracking volume trends.</p>
    </div>
  </div>

</div>
</div><!-- /info tab -->
<!-- ══════════════════════════ FUEL TAB ══════════════════════════ -->
<div class="tab-page" id="tab-fuel">

  <div class="perf-loading" id="fuelLoading">
    <div class="spin"></div>
    <div class="lmsg">building your fuel plan...</div>
  </div>

  <div id="fuelContent" style="display:none">

    <!-- Header bar -->
    <div class="row" style="margin-bottom:6px">
      <div class="panel">
        <div class="ph" style="justify-content:space-between;flex-wrap:wrap;gap:6px">
          <span class="pt">Fuel Plan</span>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <span id="fuelGCStatus"></span>
            <span style="font-size:.68rem;color:var(--muted)">Weight: <span id="fuelWeight">—</span></span>
            <div style="display:flex;gap:4px;align-items:center">
              <input id="fuelWeightInput" type="number" placeholder="lbs"
                style="width:64px;background:var(--bg2);border:1px solid var(--border2);color:var(--text);font-family:var(--mono);font-size:.68rem;padding:2px 6px;border-radius:2px"
                onkeydown="if(event.key==='Enter')updateWeight()">
              <button class="insight-btn" onclick="updateWeight()">set</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Today tiles — horizontal scroll on mobile -->
    <div style="overflow-x:auto;margin-bottom:6px;-webkit-overflow-scrolling:touch">
      <div style="display:flex;gap:6px;min-width:max-content;padding-bottom:2px">
        <div class="panel" style="min-width:120px"><div class="tile"><div class="tlabel">Today</div><div id="fuel-today-type" class="tval sm or">—</div><div class="tsub">day type</div></div></div>
        <div class="panel" style="min-width:110px"><div class="tile"><div class="tlabel">Calories</div><div id="fuel-today-cal" class="tval sm or">—</div><div class="tsub">target</div></div></div>
        <div class="panel" style="min-width:100px"><div class="tile"><div class="tlabel">Carbs</div><div id="fuel-today-carbs" class="tval sm bl">—</div><div class="tsub">grams</div></div></div>
        <div class="panel" style="min-width:100px"><div class="tile"><div class="tlabel">Protein</div><div id="fuel-today-protein" class="tval sm gr">—</div><div class="tsub">grams</div></div></div>
        <div class="panel" style="min-width:90px"><div class="tile"><div class="tlabel">Fat</div><div id="fuel-today-fat" class="tval sm">—</div><div class="tsub">grams</div></div></div>
      </div>
    </div>

    <!-- Calendar strip + detail -->
    <!-- 21-day strip — full width -->
    <div style="margin-bottom:6px">
      <div style="background:var(--surface);border:1px solid var(--border);border-radius:2px">
        <div class="ph"><span class="pt">21-Day Plan</span><span class="ptag">past 7 · today · next 13 · click any day</span></div>
        <div style="padding:8px 6px;overflow-x:auto">
          <div id="fuelStrip" class="fuel-strip"></div>
        </div>
        <div style="display:flex;align-items:center;gap:10px;padding:6px 10px;font-size:.62rem;color:var(--muted)">
          <span style="display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;background:var(--red);display:inline-block"></span>Rest/Low</span>
          <span style="display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;background:var(--yellow);display:inline-block"></span>Easy/Mod</span>
          <span style="display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block"></span>Hard/Long</span>
          <span style="margin-left:auto;color:var(--muted)">◆ Runna &nbsp; ● Strava</span>
        </div>
      </div>
    </div>

    <!-- Day detail — full width below -->
    <div class="panel">
      <div class="ph"><span class="pt">Day Detail</span></div>
      <div id="fuelDetail" style="padding:10px 12px;font-size:.75rem">
        <div style="color:var(--muted);padding:20px 0;text-align:center">Select a day</div>
      </div>
    </div>

  </div>
</div><!-- /fuel tab -->
<!-- ══════════════════════════ TRAIN TAB ══════════════════════════ -->
<div class="tab-page" id="tab-train">

  <div class="perf-loading" id="trainLoading">
    <div class="spin"></div>
    <div class="lmsg">building your training week...</div>
  </div>

  <div id="trainContent" style="display:none">

    <!-- Cache status bar -->
    <div class="train-cache-bar">
      <span id="trainCacheStatus">Loading class library...</span>
      <button class="insight-btn" onclick="refreshPelotonCache()" id="trainRefreshBtn">↺ Refresh library</button>
      <span style="margin-left:auto" id="trainGCStatus"></span>
    </div>

    <!-- 7-day week grid -->
    <div class="panel" style="margin-bottom:12px">
      <div class="ph">
        <span class="pt">This Week</span>
        <span class="ptag">Runna runs · Peloton cross-training · Core daily</span>
      </div>
      <div style="padding:10px 10px 6px;overflow-x:auto;-webkit-overflow-scrolling:touch">
        <div id="trainWeekGrid" class="train-week" style="min-width:max-content"></div>
      </div>
      <div style="display:flex;gap:12px;padding:6px 12px 10px;font-size:.62rem;color:var(--muted);flex-wrap:wrap">
        <span style="display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;background:var(--orange);display:inline-block"></span>Strava</span>
        <span style="display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;background:var(--blue);display:inline-block"></span>Runna planned</span>
        <span style="display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;background:var(--purple);display:inline-block"></span>Peloton recommended</span>
        <span style="display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:2px;background:rgba(87,148,242,.4);display:inline-block"></span>Core add-on</span>
      </div>
    </div>

  </div>
</div><!-- /train tab -->
<!-- ══════════════════════════ MEALS TAB ══════════════════════════ -->
<div class="tab-page" id="tab-meals">

  <div class="perf-loading" id="mealsLoading">
    <div class="spin"></div>
    <div class="lmsg">loading meal plans...</div>
  </div>

  <div id="mealsContent" style="display:none">

    <!-- Controls -->
    <div class="row" style="margin-bottom:6px">
      <div class="panel">
        <div class="ph" style="justify-content:space-between;flex-wrap:wrap;gap:8px">
          <span class="pt">Meal Plans</span>
          <div class="meals-controls">
            <select id="mealsPlanSelect" class="meals-select" onchange="onMealsPlanChange()">
              <option value="standard_7day">Standard High-Protein — 7-Day Periodized</option>
              <option value="standard_30day">Standard High-Protein — 30-Day</option>
              <option value="paleo_30day">Paleo — 30-Day</option>
            </select>
            <span id="mealsPlanDesc" style="font-size:.65rem;color:var(--muted)"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Day tabs -->
    <div id="mealsDayTabs" class="meals-day-tabs"></div>

    <!-- Day summary bar -->
    <div id="mealsDaySummary" class="meals-day-summary" style="display:none">
      <div class="mds-item"><div class="mds-val" id="mds-cal" style="color:var(--orange)">—</div><div class="mds-label">kcal</div></div>
      <div class="mds-item"><div class="mds-val" id="mds-carbs" style="color:var(--blue)">—</div><div class="mds-label">carbs</div></div>
      <div class="mds-item"><div class="mds-val" id="mds-protein" style="color:var(--green)">—</div><div class="mds-label">protein</div></div>
      <div class="mds-item"><div class="mds-val" id="mds-fat" style="color:var(--muted2)">—</div><div class="mds-label">fat</div></div>
      <div class="mds-item" style="margin-left:auto"><div class="mds-val" id="mds-type" style="font-size:.75rem">—</div><div class="mds-label">day type</div></div>
    </div>

    <!-- Meal cards -->
    <div id="mealCards" class="meal-grid"></div>

  </div>
</div><!-- /meals tab -->



</div><!-- /dash-tab -->

<!-- drawer -->
<div class="drawer" id="drawer">
  <div class="drawer-topbar">
    <div class="drawer-title" id="drawerTitle">Run Detail</div>
    <button class="drawer-close" onclick="closeDrawer()">✕ close</button>
  </div>
  <div class="drawer-body" id="drawerBody">
    <div class="drawer-loading"><div class="spin"></div><div class="lmsg">loading run data...</div></div>
  </div>
</div>

<script src="/static/dashboard.js"></script>
</body></html>"""


if __name__ == "__main__":
    if not CLIENT_ID() or not CLIENT_SECRET():
        print("\n⚠️  Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
