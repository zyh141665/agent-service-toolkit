from datetime import datetime

from agents.tools import current_datetime


def test_current_datetime_tool_returns_timezone_aware_iso_string():
    result = current_datetime.invoke({})

    parsed_datetime = datetime.fromisoformat(result)
    assert parsed_datetime.tzinfo is not None
