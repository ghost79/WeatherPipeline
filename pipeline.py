import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import questionary
import requests
from requests.exceptions import HTTPError

CITIES = {
    "Oslo": (59.91, 10.75),
    "Bergen": (60.39, 5.32),
    "Trondheim": (63.43, 10.39),
    "Tromsø": (69.65, 18.96)
}

API_URL = "https://api.open-meteo.com/v1/forecast"

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "weather.duckdb"

logger = logging.getLogger(__name__)

def extract(lat, lon, start_date, end_date):
    """Fetch hourly weather for one location over an inclusive date range."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": "Europe/Oslo",
    }

    try:
        response = requests.get(API_URL, params=params)

        response.raise_for_status()

        return response.json()

    except HTTPError as http_err:
        logger.error("HTTP error occurred: %s", http_err)

    except Exception as err:
        logger.error("An error occurred: %s", err)

def transform(raw, city):
    data_frame = pd.DataFrame(raw["hourly"])
    data_frame["time"] = pd.to_datetime(data_frame["time"])
    data_frame = data_frame.rename(columns={
        "temperature_2m": "temperature_c",
        "precipitation": "precipitation_mm",
        "wind_speed_10m": "wind_speed_kmh",
    })
    data_frame = data_frame.dropna()
    data_frame["city"] = city

    return data_frame

def load(all_data, start_date, end_date):
    """Idempotently load rows into DuckDB.

    Deletes existing rows for the fetched cities within the date range, then
    inserts the new ones, all in one transaction. Running it twice for the same
    range therefore leaves the table unchanged.
    """
    DATA_DIR.mkdir(exist_ok=True)
    cities = all_data["city"].unique().tolist()

    con = duckdb.connect(str(DB_PATH))
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS weather (
                time TIMESTAMP,
                temperature_c DOUBLE,
                precipitation_mm DOUBLE,
                wind_speed_kmh DOUBLE,
                city VARCHAR,
                PRIMARY KEY (city, time)
            )
        """)

        con.begin()
        deleted = con.execute(
            """
            DELETE FROM weather
            WHERE list_contains(?, city)
              AND CAST(time AS DATE) BETWEEN ? AND ?
            RETURNING 1
            """,
            [cities, start_date, end_date],
        ).fetchall()
        con.execute("INSERT INTO weather BY NAME SELECT * FROM all_data")
        con.commit()

        total = con.execute("SELECT count(*) FROM weather").fetchone()[0]
    except Exception:
        con.rollback()
        logger.exception("Database execution failed - rolled back to previous state")
        raise
    finally:
        con.close()

    logger.info("Replaced %d rows with %d in %s "
                "(table now has %d rows)", len(deleted), len(all_data), DB_PATH, total)

def parse_date(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"'{value}' is not a valid date, expected YYYY-MM-DD"
        )

def prompt_date(label, default):
    """Ask for a date, pre-filled with the default; enter accepts it."""
    def is_valid(value):
        try:
            date.fromisoformat(value)
            return True
        except ValueError:
            return "Expected a date in the format YYYY-MM-DD"

    answer = questionary.text(
        f"{label} (YYYY-MM-DD):",
        default=default.isoformat(),
        validate=is_valid,
    ).ask()

    if answer is None:  # Ctrl-C
        sys.exit(1)
    return date.fromisoformat(answer)

def select_cities():
    """Prompt for cities: arrows to move, space to toggle, 'All' at the bottom."""
    all_label = "All"
    selected = questionary.checkbox(
        "Select cities (space to toggle, enter to confirm):",
        choices=[*CITIES, questionary.Choice(all_label)],
    ).ask()

    if selected is None:  # Ctrl-C
        sys.exit(1)
    if all_label in selected:
        return list(CITIES)
    return selected

def main(cities, start_date, end_date):
    frames = []

    logger.info("Fetching weather data")
    for city in cities:
        lat, lon = CITIES[city]
        logger.info("City: %s", city)
        raw = extract(lat, lon, start_date, end_date)

        if raw is None:
            logger.warning("No data for %s", city)
            continue

        df = transform(raw, city)
        frames.append(df)

    if not frames:
        sys.exit("No data fetched, nothing to load.")

    all_data = pd.concat(frames)
    logger.info("Shape: %s", all_data.shape)
    logger.debug("dtypes: %s", all_data.dtypes)
    logger.debug("Sum: %s", all_data.isna().sum())

    load(all_data, start_date, end_date)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

    today = date.today()
    parser = argparse.ArgumentParser(description="Fetch weather data into DuckDB.")
    parser.add_argument("--from", dest="start_date", type=parse_date,
                        help="start date, YYYY-MM-DD (prompted, default today, if omitted)")
    parser.add_argument("--to", dest="end_date", type=parse_date,
                        help="end date, YYYY-MM-DD (prompted, default today, if omitted)")
    args = parser.parse_args()

    start_date = args.start_date or prompt_date("From date", today)
    end_date = args.end_date or prompt_date("To date", max(today, start_date))

    if start_date > end_date:
        parser.error("the start date must not be after the end date")

    cities = select_cities()
    if not cities:
        parser.error("no cities selected")

    main(cities, start_date, end_date)