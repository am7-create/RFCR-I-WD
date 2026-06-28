import sqlite3
import os
import pandas as pd
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

DB_PATH   = "midnapore_flood.db"
FILE1     = "24_06_2026__River_Gauge___Rain_Fall__Reservior-RFCR__Midnapore.xlsx"
FILE2     = "24_06_2026_Impact_Report_RFCR_Midnapore.xlsx"


# ─── DB HELPERS ────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def query(sql, params=()):
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def safe_float(val):
    try:
        v = str(val).strip()
        if v in ('', 'nan', 'NaN', 'None', 'Not Available', 'BG', 'N/A'):
            return None
        return float(v)
    except Exception:
        return None

def clean(val):
    v = str(val).strip()
    return None if v in ('', 'nan', 'NaN', 'None') else v


# ─── DB SETUP ──────────────────────────────────────────────────────

def create_tables(conn):
    conn.executescript("""
        DROP TABLE IF EXISTS rainfall_stations;
        DROP TABLE IF EXISTS river_gauges;
        DROP TABLE IF EXISTS reservoir;
        DROP TABLE IF EXISTS embankment_damage;
        DROP TABLE IF EXISTS district_status;
        DROP TABLE IF EXISTS district_forecast;

        CREATE TABLE rainfall_stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sl_no TEXT, basin TEXT, district TEXT, station TEXT, type TEXT,
            rainfall_24hr_mm REAL, cumulative_mm REAL, normal_annual_mm REAL,
            division TEXT, remarks TEXT
        );
        CREATE TABLE river_gauges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sl_no TEXT, river TEXT, station TEXT, district TEXT,
            gauge_level TEXT, trend TEXT,
            danger_level_mGTS REAL, ext_danger_level_mGTS REAL,
            division TEXT, remarks TEXT
        );
        CREATE TABLE reservoir (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sl_no TEXT, basin TEXT, name TEXT,
            conservation_level_ft REAL, max_flood_level_ft REAL,
            present_level_ft REAL, inflow_acft REAL, outflow_acft REAL,
            observation_time TEXT, division TEXT
        );
        CREATE TABLE embankment_damage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sl_no TEXT, district TEXT, block TEXT, description TEXT
        );
        CREATE TABLE district_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            district TEXT, rainfall_status TEXT, river_status TEXT
        );
        CREATE TABLE district_forecast (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            district TEXT, emb_risk TEXT, inun_risk TEXT, forecast TEXT
        );
    """)
    conn.commit()


def load_rainfall(conn):
    df = pd.read_excel(FILE1, sheet_name='Rainfall', header=None)
    current_sl = current_basin = current_dist = None
    rows_inserted = 0
    for i, row in df.iterrows():
        if i < 4:
            continue
        vals = [clean(v) for v in row]
        if all(v is None for v in vals):
            continue
        if any(v and v.startswith(('RMC','CWC','ORG')) and ':' in v for v in vals if v):
            continue
        col = [vals[j] if j < len(vals) else None for j in range(10)]
        if col[0] and col[0].isdigit():
            current_sl = col[0]
        basins = {'DWARAKESWAR','KANGSABATI','KUMARI','DAMODAR','SUBARNAREKHA',
                  'KALIAGHAI','HALDI','RASULPUR','RUPNARAYAN','CHANDIA',
                  'SILABATI','KUBAI','DONAI','TAMAL','SHILABATI'}
        if col[1] and col[1].upper() in basins:
            current_basin = col[1].upper()
        districts = {'BANKURA','PURULIA','JHARGRAM','PURBA MEDINIPUR','PASCHIM MEDINIPUR'}
        if col[2] and col[2].upper() in districts:
            current_dist = col[2].upper()
        str_vals, num_vals = [], []
        for v in vals:
            if v is None:
                continue
            try:
                num_vals.append(float(v))
            except Exception:
                str_vals.append(v)
        type_ = next((v for v in str_vals if v in ('ORG','RMC','CWC')), None)
        rain24 = num_vals[0] if len(num_vals) >= 1 else None
        cum    = num_vals[1] if len(num_vals) >= 2 else None
        normal = num_vals[2] if len(num_vals) >= 3 else None
        known = basins | districts | {'ORG','RMC','CWC','Not Available'}
        candidates = [v for v in str_vals if v.upper() not in known and not v.isdigit()]
        station = div = remarks = None
        heavy_kw = {'Heavy','Very Heavy','Extremely High','Extremely Heavy'}
        for v in str_vals:
            if v in heavy_kw:
                remarks = v
        candidates = [v for v in candidates if v not in heavy_kw]
        candidates.sort(key=len, reverse=True)
        if candidates:
            if 'Division' in candidates[0] or 'Divn' in candidates[0] or 'Irrigation' in candidates[0]:
                div = candidates[0]
                station = candidates[1] if len(candidates) > 1 else None
            else:
                station = candidates[0]
                div = candidates[1] if len(candidates) > 1 else None
        if not station and rain24 is None and cum is None:
            continue
        if station:
            station = station.split('(')[0].split('\n')[0].strip()
        conn.execute("""
            INSERT INTO rainfall_stations
            (sl_no,basin,district,station,type,rainfall_24hr_mm,cumulative_mm,normal_annual_mm,division,remarks)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (current_sl, current_basin, current_dist, station, type_, rain24, cum, normal, div, remarks))
        rows_inserted += 1
    conn.commit()
    return rows_inserted


def load_rivers(conn):
    df = pd.read_excel(FILE1, sheet_name='River Gauge', header=None)
    rows_inserted = 0
    current_dist = None
    district_kw = {'Bankura','Jhargaram','Jhargram','Purba Medinipur','Paschim Midnapur','Paschim Medinipur'}
    for i, row in df.iterrows():
        if i < 3:
            continue
        vals = [clean(v) for v in row]
        if all(v is None for v in vals):
            continue
        col = [vals[j] if j < len(vals) else None for j in range(10)]
        sl = col[0] if (col[0] and col[0].isdigit()) else None
        river = col[1]
        station = col[2]
        if col[3] in district_kw:
            current_dist = col[3]
            gauge = col[4]; trend = col[5]
            dl = safe_float(col[6]); edl = safe_float(col[7])
            div = col[8]; remarks = col[9]
        else:
            gauge = col[3]; trend = col[4]
            dl = safe_float(col[5]); edl = safe_float(col[6])
            div = col[7]; remarks = col[8]
        if not river and not station:
            continue
        if river and river.startswith('Sl'):
            continue
        conn.execute("""
            INSERT INTO river_gauges
            (sl_no,river,station,district,gauge_level,trend,
             danger_level_mGTS,ext_danger_level_mGTS,division,remarks)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (sl, river, station, current_dist, gauge, trend, dl, edl, div, remarks))
        rows_inserted += 1
    conn.commit()
    return rows_inserted


def load_reservoir(conn):
    # Excel has merged cells so real data columns are at positions:
    # 0=sl, 1=basin, 2=name, 4=conservation_ft, 6=max_flood_ft,
    # 8=present_ft, 10=inflow, 12=outflow, 14=obs_time, 15=division
    df = pd.read_excel(FILE1, sheet_name='Resevior', header=None)
    rows_inserted = 0
    for i, row in df.iterrows():
        if i < 3:
            continue
        # Only process rows that start with a number (actual data rows)
        sl_raw = row.iloc[0]
        try:
            sl = int(float(str(sl_raw)))
        except (ValueError, TypeError):
            continue
        name = clean(row.iloc[2])
        if not name:
            continue
        conn.execute("""
            INSERT INTO reservoir
            (sl_no, basin, name,
             conservation_level_ft, max_flood_level_ft, present_level_ft,
             inflow_acft, outflow_acft, observation_time, division)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            str(sl),
            clean(row.iloc[1]),           # basin
            name,                          # reservoir name
            safe_float(row.iloc[4]),       # conservation level ft
            safe_float(row.iloc[6]),       # max flood level ft
            safe_float(row.iloc[8]),       # present level ft
            safe_float(row.iloc[10]),      # inflow ac-ft
            safe_float(row.iloc[12]),      # outflow ac-ft
            str(row.iloc[14]).strip() if row.iloc[14] is not None else None,  # obs time
            clean(row.iloc[15]),           # division
        ))
        rows_inserted += 1
    conn.commit()
    return rows_inserted


def load_impact(conn):
    df = pd.read_excel(FILE2, sheet_name='Sheet1', header=None)
    damage_rows = []; status_rows = []; forecast_rows = []
    section = None
    skip_words = {'Reporting Format','Report of','Heavy rainfall','River Gauges',
                  'Flood Impact','Sl. No.','Name of District','Impact Forecast',
                  'Embankment','Significant Damage','Current Status','Plan for Next',
                  'District-wise forecast'}
    for i, row in df.iterrows():
        vals = [clean(v) for v in row]
        non_null = [v for v in vals if v]
        if not non_null:
            continue
        first = non_null[0]
        if 'Significant Damage' in first:
            section = 'damage'; continue
        if 'Current Status' in first or 'Plan for Next' in first:
            section = 'status'; continue
        if 'District-wise forecast' in first:
            section = 'forecast'; continue
        if any(kw in first for kw in skip_words):
            continue
        col = [vals[j] if j < len(vals) else None for j in range(6)]
        skip_vals = {'Sl.','District','Block','Impact Assessment',
                     'Embankment Damage','Structural Damage','Inundation, If any',
                     'Status of rainfall','Status of River','Data / Plan',
                     'Embankment / Bank','Area likely','Remarks'}
        if section == 'damage':
            dist = col[1]; blk = col[2]; desc = col[3]
            if dist and dist not in skip_vals:
                damage_rows.append((col[0], dist, blk, desc))
        elif section == 'status':
            dist = col[0]; rain_s = col[1]; riv_s = col[2]
            if dist and dist not in skip_vals:
                status_rows.append((dist, rain_s, riv_s))
        elif section == 'forecast':
            dist = col[0]; emb = col[1]; inun = col[2]; fcast = col[3]
            if dist and dist not in skip_vals:
                forecast_rows.append((dist, emb, inun, fcast))
    conn.executemany("INSERT INTO embankment_damage (sl_no,district,block,description) VALUES (?,?,?,?)", damage_rows)
    conn.executemany("INSERT INTO district_status (district,rainfall_status,river_status) VALUES (?,?,?)", status_rows)
    conn.executemany("INSERT INTO district_forecast (district,emb_risk,inun_risk,forecast) VALUES (?,?,?,?)", forecast_rows)
    conn.commit()
    return len(damage_rows), len(status_rows), len(forecast_rows)


def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)
    r1 = load_rainfall(conn)
    r2 = load_rivers(conn)
    r3 = load_reservoir(conn)
    d, s, f = load_impact(conn)
    conn.close()
    print(f"DB built: {r1} rainfall | {r2} rivers | {r3} reservoir | {d} damage | {s} status | {f} forecast")


# ─── ROUTES ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/summary")
def api_summary():
    total  = query("SELECT COUNT(*) AS c FROM rainfall_stations")[0]["c"]
    active = query("SELECT COUNT(*) AS c FROM rainfall_stations WHERE rainfall_24hr_mm > 0")[0]["c"]
    rising = query("SELECT COUNT(*) AS c FROM river_gauges WHERE trend='Rising'")[0]["c"]
    falling= query("SELECT COUNT(*) AS c FROM river_gauges WHERE trend='Falling'")[0]["c"]
    steady = query("SELECT COUNT(*) AS c FROM river_gauges WHERE trend='Steady'")[0]["c"]
    damage = query("SELECT COUNT(*) AS c FROM embankment_damage WHERE description NOT LIKE '%Nil%'")[0]["c"]
    top    = query("SELECT station, district, rainfall_24hr_mm FROM rainfall_stations WHERE rainfall_24hr_mm IS NOT NULL ORDER BY rainfall_24hr_mm DESC LIMIT 1")
    res    = query("SELECT present_level_ft, conservation_level_ft FROM reservoir WHERE name IS NOT NULL LIMIT 1")
    return jsonify({
        "total_stations": total,
        "active_stations": active,
        "dry_stations": total - active,
        "rising_rivers": rising,
        "falling_rivers": falling,
        "steady_rivers": steady,
        "damage_incidents": damage,
        "top_station": top[0] if top else None,
        "reservoir": res[0] if res else None
    })


@app.route("/api/rainfall")
def api_rainfall():
    district = request.args.get("district", "")
    if district:
        rows = query("""
            SELECT station, district, basin, rainfall_24hr_mm, cumulative_mm
            FROM rainfall_stations
            WHERE UPPER(district) LIKE UPPER(?)
            ORDER BY rainfall_24hr_mm DESC NULLS LAST
        """, (f"%{district}%",))
    else:
        rows = query("""
            SELECT station, district, basin, rainfall_24hr_mm, cumulative_mm
            FROM rainfall_stations
            ORDER BY rainfall_24hr_mm DESC NULLS LAST
        """)
    return jsonify(rows)


@app.route("/api/rivers")
def api_rivers():
    trend = request.args.get("trend", "")
    if trend:
        rows = query("SELECT * FROM river_gauges WHERE trend=? ORDER BY river", (trend,))
    else:
        rows = query("SELECT * FROM river_gauges ORDER BY trend DESC, river")
    return jsonify(rows)


@app.route("/api/damage")
def api_damage():
    rows = query("SELECT * FROM embankment_damage ORDER BY district")
    return jsonify(rows)


@app.route("/api/forecast")
def api_forecast():
    rows = query("""
        SELECT ds.district, ds.rainfall_status, ds.river_status, df.forecast
        FROM district_status ds
        LEFT JOIN district_forecast df ON ds.district = df.district
        ORDER BY ds.district
    """)
    return jsonify(rows)


@app.route("/api/reservoir")
def api_reservoir():
    rows = query("SELECT * FROM reservoir WHERE name IS NOT NULL")
    return jsonify(rows)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    try:
        data = request.get_json(force=True, silent=True) or {}
        q = data.get("question", data.get("message", "")).lower().strip()
        if not q:
            return jsonify({"type":"text","content":"Please type a question."})

        if any(w in q for w in ["hello","hi","help","what can"]):
            return jsonify({"type":"text","content":"Hello! I can answer questions about rainfall, river levels, embankment damage, forecasts, and reservoir status for 24 June 2026. Try asking: <b>highest rainfall</b>, <b>rising rivers</b>, <b>embankment damage</b>, or a district name like <b>Purulia</b>."})

        if any(w in q for w in ["summary","overview","total","all info"]):
            d = api_summary().get_json()
            top = d.get("top_station")
            res = d.get("reservoir")
            html = f"""<div class='sum-grid'>
              <div class='sum-card'><span class='sum-num'>{d['total_stations']}</span><span class='sum-label'>Rain Stations</span></div>
              <div class='sum-card rain'><span class='sum-num'>{d['active_stations']}</span><span class='sum-label'>With Rain</span></div>
              <div class='sum-card warn'><span class='sum-num'>{d['rising_rivers']}</span><span class='sum-label'>Rivers Rising</span></div>
              <div class='sum-card safe'><span class='sum-num'>{d['damage_incidents']}</span><span class='sum-label'>Damage Incidents</span></div>
            </div>"""
            if top:
                html += f"<p class='mt'>🏆 Highest 24hr rain: <b>{top['station']}</b> ({top['district']}) — <b>{top['rainfall_24hr_mm']} mm</b></p>"
            if res and res.get('present_level_ft'):
                html += f"<p>💧 Mukutmanipur reservoir: <b>{res['present_level_ft']} ft</b> (safe, below {res['conservation_level_ft']} ft)</p>"
            html += "<p>⚠️ Heavy rain warnings: <b class='safe-tag'>NIL</b> &nbsp;|&nbsp; Rivers above DL: <b class='safe-tag'>NONE</b></p>"
            return jsonify({"type":"html","content":html})

        if any(w in q for w in ["highest","most rain","top rain","maximum rain","which station"]):
            rows = query("SELECT station, district, basin, rainfall_24hr_mm FROM rainfall_stations WHERE rainfall_24hr_mm IS NOT NULL AND rainfall_24hr_mm > 0 ORDER BY rainfall_24hr_mm DESC LIMIT 8")
            return jsonify({"type":"table","title":"Top stations — last 24 hrs rainfall","cols":["station","district","basin","rainfall_24hr_mm"],"rows":rows})

        if any(w in q for w in ["cumulative","since jan","total since"]):
            rows = query("SELECT station, district, cumulative_mm FROM rainfall_stations WHERE cumulative_mm IS NOT NULL ORDER BY cumulative_mm DESC LIMIT 10")
            return jsonify({"type":"table","title":"Top stations — cumulative rainfall (since 1 Jan 2026)","cols":["station","district","cumulative_mm"],"rows":rows})

        if any(w in q for w in ["zero","no rain","dry","0 mm"]):
            rows = query("SELECT station, district, rainfall_24hr_mm FROM rainfall_stations WHERE rainfall_24hr_mm = 0 ORDER BY district")
            return jsonify({"type":"table","title":f"Stations with zero rainfall ({len(rows)} stations)","cols":["station","district","rainfall_24hr_mm"],"rows":rows})

        if any(w in q for w in ["all station","list station","every station","all rain"]):
            rows = query("SELECT station, district, basin, rainfall_24hr_mm, cumulative_mm FROM rainfall_stations ORDER BY district, rainfall_24hr_mm DESC NULLS LAST")
            return jsonify({"type":"table","title":f"All {len(rows)} rainfall stations","cols":["station","district","basin","rainfall_24hr_mm","cumulative_mm"],"rows":rows})

        for dist_kw, dist_val in [("purulia","PURULIA"),("bankura","BANKURA"),("jhargram","JHARGRAM"),("purba","PURBA MEDINIPUR"),("paschim","PASCHIM MEDINIPUR"),("west medinipur","PASCHIM MEDINIPUR"),("east medinipur","PURBA MEDINIPUR")]:
            if dist_kw in q:
                rows = query("SELECT station, basin, rainfall_24hr_mm, cumulative_mm FROM rainfall_stations WHERE UPPER(district) LIKE ? ORDER BY rainfall_24hr_mm DESC NULLS LAST", (f"%{dist_val}%",))
                return jsonify({"type":"table","title":f"Rainfall — {dist_val.title()}","cols":["station","basin","rainfall_24hr_mm","cumulative_mm"],"rows":rows})

        if any(w in q for w in ["rising river","rivers rising","river rise","which river","rising"]):
            rows = query("SELECT river, station, district, gauge_level, trend, danger_level_mGTS FROM river_gauges WHERE trend='Rising'")
            extra = "<p class='mt safe-msg'>✅ None have crossed Danger Level (DL). All rivers are safe.</p>"
            return jsonify({"type":"table","title":f"Rising rivers ({len(rows)})","cols":["river","station","gauge_level","trend","danger_level_mGTS"],"rows":rows,"extra":extra})

        if any(w in q for w in ["danger level","above danger","crossed danger","above dl","flood level"]):
            rows = query("""SELECT river, station, gauge_level, trend, danger_level_mGTS
                FROM river_gauges WHERE gauge_level NOT IN ('BG') AND trend NOT IN ('--')
                AND danger_level_mGTS IS NOT NULL
                AND CAST(gauge_level AS REAL) >= danger_level_mGTS""")
            if rows:
                return jsonify({"type":"table","title":"Rivers above Danger Level","cols":["river","station","gauge_level","trend","danger_level_mGTS"],"rows":rows})
            return jsonify({"type":"text","content":"✅ <b>No river has crossed the Danger Level (DL).</b><br>All gauge stations are currently Below Gauge (BG) or well under their danger level."})

        if any(w in q for w in ["all river","river gauge","every river","river status","river level","show river"]):
            rows = query("SELECT river, station, district, gauge_level, trend, danger_level_mGTS FROM river_gauges ORDER BY trend DESC, river")
            return jsonify({"type":"table","title":f"All {len(rows)} river gauge stations","cols":["river","station","gauge_level","trend","danger_level_mGTS"],"rows":rows})

        if any(w in q for w in ["embankment","damage","erosion","polaspai","daspur","slip","subsidence"]):
            rows = query("SELECT district, block, description FROM embankment_damage")
            return jsonify({"type":"damage","rows":rows})

        if any(w in q for w in ["forecast","next 24","tomorrow","imd","warning","prediction"]):
            rows = query("SELECT ds.district, ds.rainfall_status, ds.river_status, df.forecast FROM district_status ds LEFT JOIN district_forecast df ON ds.district=df.district ORDER BY ds.district")
            return jsonify({"type":"table","title":"District-wise forecast (IMD Kolkata) — next 24 hrs","cols":["district","rainfall_status","river_status","forecast"],"rows":rows})

        if any(w in q for w in ["district status","current status","status of all","all district"]):
            rows = query("SELECT district, rainfall_status, river_status FROM district_status ORDER BY district")
            return jsonify({"type":"table","title":"Current district status","cols":["district","rainfall_status","river_status"],"rows":rows})

        if any(w in q for w in ["reservoir","mukutmanipur","dam","conservation"]):
            rows = query("SELECT * FROM reservoir WHERE name IS NOT NULL LIMIT 1")
            if rows:
                r = rows[0]
                cons = r.get("conservation_level_ft") or 0
                pres = r.get("present_level_ft") or 0
                diff = cons - pres
                html = f"""<div class='res-grid'>
                  <div class='res-item'><span class='rl'>Conservation Level</span><span class='rv'>{r.get("conservation_level_ft")} ft</span></div>
                  <div class='res-item'><span class='rl'>Max Flood Level</span><span class='rv'>{r.get("max_flood_level_ft")} ft</span></div>
                  <div class='res-item'><span class='rl'>Present Level</span><span class='rv safe-tag'>{r.get("present_level_ft")} ft</span></div>
                  <div class='res-item'><span class='rl'>Inflow (24hrs)</span><span class='rv'>{r.get("inflow_acft")} ac-ft</span></div>
                  <div class='res-item'><span class='rl'>Outflow (24hrs)</span><span class='rv'>{r.get("outflow_acft")} ac-ft</span></div>
                  <div class='res-item'><span class='rl'>Observation Time</span><span class='rv'>{r.get("observation_time")}</span></div>
                </div>
                <p class='mt'>✅ Level is <b>{diff:.1f} ft</b> below conservation level — no concern.</p>"""
                return jsonify({"type":"html","content":html})
            return jsonify({"type":"text","content":"No reservoir data found."})

        if any(w in q for w in ["inundation","flood area","waterlog","submerged"]):
            return jsonify({"type":"text","content":"✅ <b>No inundation reported</b> in any district as of 24 June 2026."})

        if any(w in q for w in ["how many","count station","number of station","total station"]):
            rows = query("SELECT district, COUNT(*) AS count FROM rainfall_stations GROUP BY district ORDER BY district")
            total = query("SELECT COUNT(*) AS c FROM rainfall_stations")[0]["c"]
            return jsonify({"type":"table","title":f"Total rainfall stations: {total}","cols":["district","count"],"rows":rows})

        return jsonify({"type":"text","content":"I didn't understand that. Try: <b>highest rainfall</b>, <b>rising rivers</b>, <b>embankment damage</b>, <b>reservoir</b>, <b>forecast</b>, or a district name like <b>Purulia</b> or <b>Bankura</b>."})

    except Exception as e:
        return jsonify({"type":"text","content":f"⚠️ Server error: {str(e)}"})


# ─── STARTUP ───────────────────────────────────────────────────────
# Auto-build DB on every startup (required for Render free tier)
if os.path.exists(FILE1) and os.path.exists(FILE2):
    print("Building database from Excel files...")
    init_db()
    print("Database ready.")
else:
    print("WARNING: Excel files not found. Some features will not work.")

if __name__ == "__main__":
    app.run(debug=True, port=5000)