import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "midnapore_flood.db")


def create_tables(conn):
    conn.executescript(
        """
        DROP TABLE IF EXISTS rainfall_stations;
        DROP TABLE IF EXISTS river_gauges;
        DROP TABLE IF EXISTS reservoir;
        DROP TABLE IF EXISTS embankment_damage;
        DROP TABLE IF EXISTS district_status;
        DROP TABLE IF EXISTS district_forecast;

        CREATE TABLE rainfall_stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sl_no INTEGER,
            basin TEXT,
            district TEXT,
            station TEXT,
            type TEXT,
            rainfall_24hr_mm REAL,
            cumulative_mm REAL,
            normal_annual_mm REAL,
            division TEXT,
            remarks TEXT
        );

        CREATE TABLE river_gauges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sl_no INTEGER,
            river TEXT,
            station TEXT,
            district TEXT,
            gauge_level TEXT,
            trend TEXT,
            danger_level_mGTS REAL,
            ext_danger_level_mGTS REAL,
            division TEXT,
            remarks TEXT
        );

        CREATE TABLE reservoir (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sl_no INTEGER,
            reservoir TEXT,
            district TEXT,
            water_level TEXT,
            trend TEXT,
            remarks TEXT,
            conservation_level_ft REAL,
            max_flood_level_ft REAL,
            present_level_ft REAL,
            inflow_acft REAL,
            outflow_acft REAL,
            observation_time TEXT,
            division TEXT
        );

        CREATE TABLE embankment_damage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sl_no INTEGER,
            district TEXT,
            block TEXT,
            description TEXT
        );

        CREATE TABLE district_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            district TEXT,
            rainfall_status TEXT,
            river_status TEXT
        );

        CREATE TABLE district_forecast (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            district TEXT,
            embankment_risk TEXT,
            inundation_risk TEXT,
            remarks TEXT
        );
        """
    )
    conn.commit()


def load_data(conn):
    rainfall = [
        (1, "DWARAKESWAR", "BANKURA", "Bankura", "ORG", None, None, 1533.9, "Bankura Irrigation Divn.", None),
        (2, "KANGSABATI", "PURULIA", "Purulia Sadar", "ORG", 1.0, 363.0, 1449.9, "Purulia Irrigation Division", None),
        (3, "SUBARNAREKHA", "JHARGRAM", "Gopiballavpur", "ORG", 0.0, 551.0, 1569.3, "JFMPD Jhargram", None),
    ]
    conn.executemany(
        """
        INSERT INTO rainfall_stations
        (sl_no, basin, district, station, type, rainfall_24hr_mm, cumulative_mm, normal_annual_mm, division, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rainfall,
    )

    rivers = [
        (1, "Dwarakeswar", "Patakhola", "Bankura", "BG", "Steady", 76.5, 77.11, "Bankura Irrigation Division", None),
        (2, "Kaliaghai", "Amgachia", "Purba Medinipur", "3.8", "Rising", 5.79, 6.4, "Contai Irrigation Division", None),
        (3, "Subarnarekha", "Gopiballavpur", "Jhargram", "BG", "Steady", 45.5, 46.5, "Jhargram Flood Management Divn.", None),
    ]
    conn.executemany(
        """
        INSERT INTO river_gauges
        (sl_no, river, station, district, gauge_level, trend, danger_level_mGTS, ext_danger_level_mGTS, division, remarks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rivers,
    )

    conn.execute(
        """
        INSERT INTO reservoir
        (sl_no, reservoir, district, water_level, trend, remarks, conservation_level_ft, max_flood_level_ft, present_level_ft, inflow_acft, outflow_acft, observation_time, division)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, "Mukutmanipur", "Bankura", "408.5", "Steady", None, 434.0, 445.0, 408.5, 0.0, 0.0, "06:00:00", "K. Canal Divn.-II"),
    )

    damage = [
        (1, "Purba Medinipur", "Nil", "Nil"),
        (2, "Paschim Medinipur", "Daspur-II", "Erosion at Polaspai embankment"),
    ]
    conn.executemany(
        """
        INSERT INTO embankment_damage (sl_no, district, block, description)
        VALUES (?, ?, ?, ?)
        """,
        damage,
    )

    status = [
        ("Purba Medinipur", "Stopped", "Nil"),
        ("Paschim Medinipur", "Stopped", "Nil"),
    ]
    conn.executemany(
        """
        INSERT INTO district_status (district, rainfall_status, river_status)
        VALUES (?, ?, ?)
        """,
        status,
    )

    forecast = [
        ("Purba Medinipur", "-", "-", "Light to moderate rain likely at a few places."),
        ("Paschim Medinipur", "-", "-", "Light to moderate rain likely at a few places."),
    ]
    conn.executemany(
        """
        INSERT INTO district_forecast (district, embankment_risk, inundation_risk, remarks)
        VALUES (?, ?, ?, ?)
        """,
        forecast,
    )

    conn.commit()
    print(f"Loaded {len(rainfall)} rainfall stations")
    print(f"Loaded {len(rivers)} river gauges")
    print("Loaded 1 reservoir")
    print(f"Loaded {len(damage)} damage records")
    print(f"Loaded {len(status)} district status records")
    print(f"Loaded {len(forecast)} district forecast records")


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed old: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    print(f"\nCreating database: {DB_PATH}\n")

    print("[1] Creating 6 tables...")
    create_tables(conn)

    print("[2] Loading all data...")
    load_data(conn)

    conn.close()

    print(f"\nDone! Database saved as: {DB_PATH}")
    print("\nRun next: python chatbot.py")


if __name__ == "__main__":
    main()
                