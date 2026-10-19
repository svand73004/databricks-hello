"""Fetch daily weather from the free Open-Meteo API (no key needed) and flatten it to rows.

Pure Python (no Spark), so the parsing is easy to unit test.
"""

from datetime import date

import requests

API_URL = "https://api.open-meteo.com/v1/forecast"

CITIES = {
    "Brussels": (50.85, 4.35),
    "Antwerp": (51.22, 4.40),
    "Ghent": (51.05, 3.72),
    "Leuven": (50.88, 4.70),
}

DAILY_FIELDS = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"]


def fetch_daily(latitude: float, longitude: float, past_days: int = 7) -> dict:
    """Return the raw API response: the last `past_days` days plus a 7-day forecast."""
    response = requests.get(
        API_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join(DAILY_FIELDS),
            "timezone": "Europe/Brussels",
            "past_days": past_days,
            "forecast_days": 7,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def parse_daily(city: str, payload: dict, today: date) -> list[dict]:
    """Turn the column-oriented 'daily' block into one row per city and date."""
    daily = payload["daily"]
    rows = []
    for i, day in enumerate(daily["time"]):
        day = date.fromisoformat(day)
        rows.append(
            {
                "city": city,
                "date": day,
                "temperature_max_c": daily["temperature_2m_max"][i],
                "temperature_min_c": daily["temperature_2m_min"][i],
                "precipitation_mm": daily["precipitation_sum"][i],
                "is_forecast": day > today,
            }
        )
    return rows


def fetch_all(today: date) -> list[dict]:
    """Fetch and parse every city in CITIES."""
    rows = []
    for city, (latitude, longitude) in CITIES.items():
        rows.extend(parse_daily(city, fetch_daily(latitude, longitude), today))
    return rows

if __name__ == "__main__":
    rows = fetch_all(today=date.today())
    for row in rows:
        print(row)

