import requests
from requests.exceptions import HTTPError
import pandas as pd
from pathlib import Path

CITIES = {
    "Oslo": (59.91, 10.75),
    "Bergen": (60.39, 5.32),
    "Trondheim": (63.43, 10.39),
    "Tromsø": (69.65, 18.96)
}

API_URL = "https://api.open-meteo.com/v1/forecast"

DATA_DIR = Path("data")

def extract(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
        "past_days": 7,
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
    Path(DATA_DIR).mkdir(exist_ok=True)

    csv_path = DATA_DIR / "weather.csv"
    parquet_path = DATA_DIR / "weather.parquet"

    all_data.to_csv(csv_path, index=False)
    all_data.to_parquet(parquet_path, index=False)

    csv_data = pd.read_csv(csv_path)
    parquet_data = pd.read_parquet(parquet_path)

    print(f">> CSV bytes: {csv_path.stat().st_size} (dtype {csv_data.dtypes})")
    print(f">> Parquet bytes: {parquet_path.stat().st_size} (dtype {parquet_data.dtypes})")

def main():
    frames = []

    print(" --- Fetching weather data --- ")
    for city, (lat, lon) in CITIES.items():
        print(f" > City: {city}")
        raw = extract(lat, lon)

        if raw is None:
            continue
        
        df = transform(raw, city)
        frames.append(df)

    all_data = pd.concat(frames)
    print(f"Shape: {all_data.shape}")
    print(f"dtypes: {all_data.dtypes}")
    print(f"Sum: {all_data.isna().sum()}")

    load(all_data)

if __name__ == "__main__":
    main()