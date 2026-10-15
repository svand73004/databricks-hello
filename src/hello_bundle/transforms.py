"""Pure-Python logic: easy to unit test without a Spark cluster."""


def add_greeting(rows: list[dict]) -> list[dict]:
    """Return new rows with a 'greeting' field added."""
    return [{**row, "greeting": f"Hello, {row['name'].strip().title()}!"} for row in rows]
