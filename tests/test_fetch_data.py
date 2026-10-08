from datetime import date, timedelta
from itertools import pairwise


def test_months_do_not_overlap(fetch_data):
    # Regression: CFPB date_received_max is inclusive, so a month must end on its
    # last day, not the 1st of the next month (that double-counted ~3%/month).
    months = fetch_data._months(date(2025, 11, 15), date(2026, 3, 2))
    assert months[0] == (date(2025, 11, 1), date(2025, 11, 30))
    assert months[2] == (date(2026, 1, 1), date(2026, 1, 31))
    assert months[3] == (date(2026, 2, 1), date(2026, 2, 28))
    assert months[-1] == (date(2026, 3, 1), date(2026, 3, 31))
    for (_, end), (next_start, _) in pairwise(months):
        assert next_start - end == timedelta(days=1)


def test_months_spans_year_boundary(fetch_data):
    months = fetch_data._months(date(2025, 12, 1), date(2026, 1, 1))
    assert [m[0] for m in months] == [date(2025, 12, 1), date(2026, 1, 1)]


def test_seeds_drive_the_fetcher(fetch_data):
    assert set(fetch_data.BANKS) == {"jpm", "bac", "wfc", "citi", "cof"}
    assert fetch_data.FOCAL["bank_id"] == "jpm"
    assert "DRCCLACBS" in fetch_data.FRED_SERIES
