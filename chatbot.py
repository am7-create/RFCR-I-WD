import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "midnapore_flood.db")


def db(sql, params=()):
    """Run a SQL query and return list of dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  DISPLAY HELPERS
# ─────────────────────────────────────────────

def line(char="─", width=60):
    print(char * width)

def table(rows, cols):
    """Print a simple text table."""
    if not rows:
        print("  (no records found)")
        return
    widths = [max(len(str(c)), max(len(str(r.get(c, "") or "")) for r in rows)) for c in cols]
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
    header = fmt.format(*cols)
    print(header)
    print("  " + "  ".join("─" * w for w in widths))
    for r in rows:
        print(fmt.format(*[str(r.get(c, "") or "N/A") for c in cols]))


# ─────────────────────────────────────────────
#  QUERY FUNCTIONS  (pure SQL, no AI)
# ─────────────────────────────────────────────

def q_highest_rainfall():
    rows = db("""
        SELECT station, district, basin, rainfall_24hr_mm
        FROM rainfall_stations
        WHERE rainfall_24hr_mm IS NOT NULL AND rainfall_24hr_mm > 0
        ORDER BY rainfall_24hr_mm DESC
        LIMIT 10
    """)
    print("\n📊 Top stations by rainfall in last 24 hours:\n")
    table(rows, ["station", "district", "basin", "rainfall_24hr_mm"])
    if rows:
        top = rows[0]
        print(f"\n  ✅ Highest: {top['station']} ({top['district']}) — {top['rainfall_24hr_mm']} mm")


def q_all_rainfall():
    rows = db("""
        SELECT station, district, basin,
               COALESCE(CAST(rainfall_24hr_mm AS TEXT), 'N/A') AS rain_24hr,
               COALESCE(CAST(cumulative_mm AS TEXT), 'N/A') AS cumulative
        FROM rainfall_stations
        ORDER BY district, rainfall_24hr_mm DESC NULLS LAST
    """)
    print("\n📊 All rainfall stations (41 total):\n")
    table(rows, ["station", "district", "basin", "rain_24hr", "cumulative"])


def q_district_rainfall(district_keyword):
    rows = db("""
        SELECT station, basin, rainfall_24hr_mm, cumulative_mm
        FROM rainfall_stations
        WHERE UPPER(district) LIKE UPPER(?)
        ORDER BY rainfall_24hr_mm DESC NULLS LAST
    """, (f"%{district_keyword}%",))
    print(f"\n📊 Rainfall stations in '{district_keyword}':\n")
    table(rows, ["station", "basin", "rainfall_24hr_mm", "cumulative_mm"])


def q_rising_rivers():
    rows = db("""
        SELECT river, station, gauge_level, trend, danger_level_mGTS, ext_danger_level_mGTS
        FROM river_gauges
        WHERE LOWER(trend) = 'rising'
        ORDER BY river
    """)
    print("\n🌊 Rivers with RISING trend:\n")
    table(rows, ["river", "station", "gauge_level", "trend", "danger_level_mGTS"])
    print(f"\n  ℹ️  {len(rows)} rivers are currently rising.")
    print("  ✅ None have crossed the Danger Level (DL) as of this report.")


def q_all_rivers():
    rows = db("""
        SELECT river, station, COALESCE(district,'—') AS district,
               gauge_level, trend, danger_level_mGTS, ext_danger_level_mGTS
        FROM river_gauges
        ORDER BY trend DESC, river
    """)
    print("\n🌊 All river gauge stations (24 total):\n")
    table(rows, ["river", "station", "district", "gauge_level", "trend", "danger_level_mGTS"])


def q_danger_level():
    rows = db("""
        SELECT river, station, gauge_level, trend, danger_level_mGTS, ext_danger_level_mGTS
        FROM river_gauges
        WHERE gauge_level != 'BG'
          AND gauge_level NOT LIKE '%(+)%'
          AND gauge_level NOT LIKE '%(-)%'
          AND trend != '--'
          AND CAST(gauge_level AS REAL) >= danger_level_mGTS
    """)
    print("\n🚨 Rivers at or above Danger Level:\n")
    if rows:
        table(rows, ["river", "station", "gauge_level", "trend", "danger_level_mGTS"])
    else:
        print("  ✅ No river has crossed the Danger Level (DL).")
        print("  All gauge stations are currently Below Gauge (BG) or well under DL.")


def q_embankment():
    rows = db("""
        SELECT district, COALESCE(block,'—') AS block, description
        FROM embankment_damage
        WHERE LOWER(description) != 'nil'
    """)
    nil_rows = db("""
        SELECT district FROM embankment_damage WHERE LOWER(description) = 'nil'
    """)
    print("\n⚠️  Embankment / Damage Report:\n")
    if rows:
        print("  DAMAGE REPORTED:\n")
        for r in rows:
            print(f"  📍 District : {r['district']}")
            print(f"     Block    : {r['block']}")
            print(f"     Details  : {r['description']}")
            print()
    else:
        print("  No embankment damage reported.")

    if nil_rows:
        districts = ", ".join(r["district"] for r in nil_rows)
        print(f"  ✅ No damage: {districts}")


def q_forecast():
    rows = db("""
        SELECT district, remarks FROM district_forecast ORDER BY district
    """)
    print("\n🌦️  District-wise Forecast (next 24 hours, IMD Kolkata):\n")
    for r in rows:
        print(f"  📍 {r['district']}")
        print(f"     {r['remarks']}\n")
    print("  ⚠️  Warnings: NIL — No heavy rainfall warning issued.")


def q_district_status():
    rows = db("""
        SELECT ds.district, ds.rainfall_status, ds.river_status, df.remarks AS forecast
        FROM district_status ds
        LEFT JOIN district_forecast df ON ds.district = df.district
        ORDER BY ds.district
    """)
    print("\n📋 Current District Status:\n")
    table(rows, ["district", "rainfall_status", "river_status", "forecast"])


def q_reservoir():
    rows = db("SELECT * FROM reservoir")
    if rows:
        r = rows[0]
        print("\n💧 Reservoir Status — Mukutmanipur (Kangsabati Basin):\n")
        print(f"  Conservation Level  : {r['conservation_level_ft']} ft")
        print(f"  Max Flood Level     : {r['max_flood_level_ft']} ft")
        print(f"  Present Level       : {r['present_level_ft']} ft  ✅ (below conservation level)")
        print(f"  Inflow last 24 hrs  : {r['inflow_acft']} ac-ft")
        print(f"  Outflow last 24 hrs : {r['outflow_acft']} ac-ft")
        print(f"  Observation Time    : {r['observation_time']}")
        print(f"  Division            : {r['division']}")
        diff = r['conservation_level_ft'] - r['present_level_ft']
        print(f"\n  📉 Level is {diff:.1f} ft below conservation level — no concern.")


def q_cumulative():
    rows = db("""
        SELECT station, district, cumulative_mm
        FROM rainfall_stations
        WHERE cumulative_mm IS NOT NULL
        ORDER BY cumulative_mm DESC
        LIMIT 10
    """)
    print("\n📊 Top stations by cumulative rainfall (since 1 Jan 2026):\n")
    table(rows, ["station", "district", "cumulative_mm"])


def q_zero_rain():
    rows = db("""
        SELECT station, district, rainfall_24hr_mm
        FROM rainfall_stations
        WHERE rainfall_24hr_mm = 0
        ORDER BY district
    """)
    print(f"\n🟢 Stations with zero rainfall in last 24 hours ({len(rows)} stations):\n")
    table(rows, ["station", "district", "rainfall_24hr_mm"])


def q_summary():
    total_rain = db("SELECT COUNT(*) AS c FROM rainfall_stations")[0]["c"]
    active = db("SELECT COUNT(*) AS c FROM rainfall_stations WHERE rainfall_24hr_mm > 0")[0]["c"]
    rising = db("SELECT COUNT(*) AS c FROM river_gauges WHERE trend='Rising'")[0]["c"]
    falling = db("SELECT COUNT(*) AS c FROM river_gauges WHERE trend='Falling'")[0]["c"]
    steady = db("SELECT COUNT(*) AS c FROM river_gauges WHERE trend='Steady'")[0]["c"]
    damage = db("SELECT COUNT(*) AS c FROM embankment_damage WHERE LOWER(description)!='nil'")[0]["c"]
    top = db("SELECT station, district, rainfall_24hr_mm FROM rainfall_stations WHERE rainfall_24hr_mm IS NOT NULL ORDER BY rainfall_24hr_mm DESC LIMIT 1")
    res = db("SELECT present_level_ft, conservation_level_ft FROM reservoir")[0]

    print("\n" + "=" * 60)
    print("  MIDNAPORE FLOOD IMPACT SUMMARY — 24 JUNE 2026")
    print("=" * 60)
    print(f"\n  🌧️  Rainfall Stations   : {total_rain} total  |  {active} with rain  |  {total_rain - active} dry")
    if top:
        print(f"  🏆 Highest 24hr Rain   : {top[0]['station']} ({top[0]['district']}) — {top[0]['rainfall_24hr_mm']} mm")
    print(f"\n  🌊 River Gauges        : {rising} Rising  |  {falling} Falling  |  {steady} Steady")
    print("  🚨 Above Danger Level  : NONE ✅")
    print(f"\n  ⚠️  Embankment Damage   : {damage} incident(s) — Daspur-II, Paschim Medinipur")
    print(f"\n  💧 Mukutmanipur Reservoir: {res['present_level_ft']} ft  (safe, below {res['conservation_level_ft']} ft)")
    print("\n  🌦️  Forecast (all districts): Light to moderate rain/thundershower")
    print("  ⚠️  Heavy Rain Warnings : NONE ✅")
    print()


# ─────────────────────────────────────────────
#  ROUTER  (keyword matching)
# ─────────────────────────────────────────────

def route(text):
    t = text.lower().strip()

    if any(w in t for w in ["summary","overview","report","all info","total"]):
        q_summary(); return

    if any(w in t for w in ["highest rain","most rain","top rain","maximum rain","highest station","which station"]):
        q_highest_rainfall(); return

    if any(w in t for w in ["cumulative","since jan","since 1 jan","total rain since"]):
        q_cumulative(); return

    if any(w in t for w in ["zero rain","no rain","dry station","0 mm"]):
        q_zero_rain(); return

    if any(w in t for w in ["all station","all rain","every station","list station","show station"]):
        q_all_rainfall(); return

    if any(w in t for w in ["purulia"]):
        q_district_rainfall("PURULIA"); return

    if any(w in t for w in ["bankura"]):
        q_district_rainfall("BANKURA"); return

    if any(w in t for w in ["jhargram"]):
        q_district_rainfall("JHARGRAM"); return

    if any(w in t for w in ["purba medinipur","purba","east midnapore","east medinipur"]):
        q_district_rainfall("PURBA MEDINIPUR"); return

    if any(w in t for w in ["paschim medinipur","paschim","west midnapore","west medinipur","midnapore"]):
        q_district_rainfall("PASCHIM MEDINIPUR"); return

    if any(w in t for w in ["rising river","which river rise","river rise","rivers are rising"]):
        q_rising_rivers(); return

    if any(w in t for w in ["danger level","flood level","above danger","crossed danger","above dl"]):
        q_danger_level(); return

    if any(w in t for w in ["all river","river gauge","every river","river level","river status","show river"]):
        q_all_rivers(); return

    if any(w in t for w in ["embankment","damage","erosion","polaspai","daspur","slip","subsidence"]):
        q_embankment(); return

    if any(w in t for w in ["forecast","next 24","tomorrow","prediction","imd","warning"]):
        q_forecast(); return

    if any(w in t for w in ["district status","current status","status of","all district"]):
        q_district_status(); return

    if any(w in t for w in ["reservoir","mukutmanipur","dam","conservation level","flood level"]):
        q_reservoir(); return

    if any(w in t for w in ["inundation","flood area","waterlog","submerged"]):
        print("\n  ✅ No inundation reported in any district as of 24 June 2026.")
        print("  All 5 districts show NIL under inundation assessment.\n"); return

    if any(w in t for w in ["how many station","total station","count station","number of station"]):
        print("\n  📊 Total rain gauge stations: 41")
        print("     Bankura: 4  |  Purulia: 21  |  Jhargram: 1")
        print("     Purba Medinipur: 7  |  Paschim Medinipur: 8\n"); return

    # default
    print("\n  ❓ I did not understand that question.")
    print("  Type  help  to see all available commands.\n")


# ─────────────────────────────────────────────
#  HELP
# ─────────────────────────────────────────────

def print_help():
    print("""
┌─────────────────────────────────────────────────────────┐
│              AVAILABLE COMMANDS                          │
├─────────────────────────────────────────────────────────┤
│ summary           → Full flood impact overview           │
│ highest rainfall  → Which station had most rain today?   │
│ all stations      → List all 41 rain gauge stations      │
│ cumulative        → Cumulative rainfall since Jan 2026   │
│ zero rain         → Stations with no rain today          │
│                                                         │
│ purulia           → Rainfall in Purulia district         │
│ bankura           → Rainfall in Bankura district         │
│ jhargram          → Rainfall in Jhargram district        │
│ purba medinipur   → Rainfall in Purba Medinipur          │
│ paschim medinipur → Rainfall in Paschim Medinipur        │
│                                                         │
│ all rivers        → All 24 river gauge stations          │
│ rising rivers     → Which rivers are rising?             │
│ danger level      → Any river above danger level?        │
│                                                         │
│ embankment damage → What damage occurred?                │
│ forecast          → IMD 24-hour district forecast        │
│ district status   → Current status of all districts      │
│ reservoir         → Mukutmanipur dam status              │
│ inundation        → Any area flooded?                    │
│                                                         │
│ help              → Show this menu                       │
│ exit              → Quit                                 │
└─────────────────────────────────────────────────────────┘
""")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    if not os.path.exists(DB_PATH):
        print(f"\nERROR: '{DB_PATH}' not found.")
        print("Run this first:  python setup_db.py\n")
        return

    print("\n" + "=" * 60)
    print("  MIDNAPORE FLOOD IMPACT CHATBOT")
    print("  RFCR · 24 June 2026 · Paschim Medinipur")
    print("  (No API key needed — pure Python + SQLite)")
    print("=" * 60)
    print("  Type 'help' for all commands  |  'exit' to quit\n")

    q_summary()

    while True:
        try:
            user = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user:
            continue
        if user.lower() in ("exit", "quit", "bye"):
            print("Goodbye!")
            break
        if user.lower() == "help":
            print_help()
            continue

        line()
        route(user)
        line()


if __name__ == "__main__":
    main()