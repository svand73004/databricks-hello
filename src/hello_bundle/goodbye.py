"""Pure-Python logic: easy to unit test without a Spark cluster."""


def add_goodbye(rows: list[dict]) -> list[dict]:
    """Return new rows with a 'greeting' field added."""
    return [{"greeting": f"Goodbye, {row['name'].strip().title()}!"} for row in rows]
