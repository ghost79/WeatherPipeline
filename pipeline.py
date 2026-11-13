import argparse
import sys
from datetime import date
from pathlib import Path

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
        print(f"HTTP error occurred: {http_err}")

    except Exception as err:
        print(f"An error occurred: {err}")

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

def load(all_data):
    DATA_DIR.mkdir(exist_ok=True)

    parquet_path = DATA_DIR / "weather.parquet"
    all_data.to_parquet(parquet_path, index=False)

    print(f">> Wrote {len(all_data)} rows to {parquet_path}")

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

    print(" --- Fetching weather data --- ")
    for city in cities:
        lat, lon = CITIES[city]
        print(f" > City: {city}")
        raw = extract(lat, lon, start_date, end_date)

        if raw is None:
            continue

        df = transform(raw, city)
        frames.append(df)

    if not frames:
        sys.exit("No data fetched, nothing to load.")

    all_data = pd.concat(frames)
    print(f"Shape: {all_data.shape}")
    print(f"dtypes: {all_data.dtypes}")
    print(f"Sum: {all_data.isna().sum()}")

    load(all_data)

if __name__ == "__main__":
    today = date.today()
    parser = argparse.ArgumentParser(description="Fetch weather data into Parquet.")
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