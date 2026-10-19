from datetime import date

from hello_bundle.weather_api import parse_daily

PAYLOAD = {
    "daily": {
        "time": ["2026-10-18", "2026-10-19", "2026-10-20"],
        "temperature_2m_max": [14.2, 15.0, None],
        "temperature_2m_min": [7.1, 8.3, 9.0],
        "precipitation_sum": [0.0, 2.4, 5.1],
    }
}


def test_parse_daily_one_row_per_day():
    rows = parse_daily("Ghent", PAYLOAD, today=date(2026, 10, 19))
    assert rows[1] == {
        "city": "Ghent",
        "date": date(2026, 10, 19),
        "temperature_max_c": 15.0,
        "temperature_min_c": 8.3,
        "precipitation_mm": 2.4,
        "is_forecast": False,
    }
    assert len(rows) == 3


def test_parse_daily_marks_future_days_as_forecast():
    rows = parse_daily("Ghent", PAYLOAD, today=date(2026, 10, 19))
    assert [r["is_forecast"] for r in rows] == [False, False, True]


def test_parse_daily_keeps_missing_values_as_none():
    rows = parse_daily("Ghent", PAYLOAD, today=date(2026, 10, 19))
    assert rows[2]["temperature_max_c"] is None
