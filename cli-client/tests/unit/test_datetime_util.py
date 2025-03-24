from datetime import datetime, timedelta

from player_ranking.datetime_util import get_season_start, get_season_end, get_time_since_last_clan_war_started


def test_get_season_start_from_mid_month():
    timestamp = datetime(2025, 3, 15, 12, 0)
    expected = datetime(2025, 3, 3, 10, 0)
    assert get_season_start(timestamp) == expected


def test_get_season_start_from_before_first_monday():
    timestamp = datetime(2025, 3, 1, 12, 0)
    expected = datetime(2025, 2, 3, 10, 0)
    assert get_season_start(timestamp) == expected


def test_get_season_start_from_on_first_monday_after_season_start():
    timestamp = datetime(2025, 3, 3, 12, 0)
    expected = datetime(2025, 3, 3, 10, 0)
    assert get_season_start(timestamp) == expected


def test_get_season_start_from_on_first_monday_before_season_start():
    timestamp = datetime(2025, 3, 3, 8, 0)
    expected = datetime(2025, 2, 3, 10, 0)
    assert get_season_start(timestamp) == expected


def test_get_season_start_from_on_end_month():
    timestamp = datetime(2025, 3, 31, 8, 0)
    expected = datetime(2025, 3, 3, 10, 0)
    assert get_season_start(timestamp) == expected


def test_get_season_start_from_on_second_monday():
    timestamp = datetime(2025, 9, 8, 8, 0)
    expected = datetime(2025, 9, 1, 10, 0)
    assert get_season_start(timestamp) == expected


def test_get_season_start_from_on_monday_as_first_day():
    timestamp = datetime(2025, 9, 1, 10, 0)
    expected = datetime(2025, 9, 1, 10, 0)
    assert get_season_start(timestamp) == expected


def test_get_long_season_end():
    timestamp = datetime(2025, 3, 3, 10, 0)
    assert get_season_end(timestamp) == (timestamp + timedelta(weeks=5))


def test_get_short_season_end():
    timestamp = datetime(2025, 4, 7, 10, 0)
    assert get_season_end(timestamp) == (timestamp + timedelta(weeks=4))


def test_get_time_since_last_clan_war_started_on_war_end():
    timestamp = datetime(2025, 3, 24, 10)
    assert get_time_since_last_clan_war_started(timestamp) == timedelta(days=4)


def test_get_time_since_last_clan_war_started_on_war_start():
    timestamp = datetime(2025, 3, 20, 10)
    assert get_time_since_last_clan_war_started(timestamp) == timedelta(seconds=0)


def test_get_time_since_last_clan_war_started_1_minute_after_start():
    timestamp = datetime(2025, 3, 20, 10, 1)
    assert get_time_since_last_clan_war_started(timestamp) == timedelta(minutes=1)


def test_get_time_since_last_clan_war_started_1_minute_before_start():
    timestamp = datetime(2025, 3, 20, 9, 59)
    assert get_time_since_last_clan_war_started(timestamp) == timedelta(days=6, hours=23, minutes=59)
