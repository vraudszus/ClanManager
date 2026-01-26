from datetime import date, datetime, time, timedelta


def get_season_start(ts: datetime) -> datetime:
    """
    Computes the start of the season (first Monday at 10 AM) for the season the given timestamp falls into.
    The provided timestamp must be in UTC.
    """
    if ts.weekday() >= ts.day or (ts.weekday() == 0 and ts.day < 8 and ts.time() < time(hour=10)):
        # the current month didn't yet have a Monday 10 AM
        prev_month_first_day: date = (ts - timedelta(weeks=1)).replace(day=1)
        prev_first_monday: date = prev_month_first_day + timedelta(
            days=(7 - prev_month_first_day.weekday()) % 7
        )
    else:
        cur_month_first_day: date = ts.replace(day=1)
        prev_first_monday: date = cur_month_first_day + timedelta(
            days=(7 - cur_month_first_day.weekday()) % 7
        )
    return datetime.combine(prev_first_monday, time(hour=10), ts.tzinfo)


def get_season_end(season_start: datetime) -> datetime:
    """
    Returns the end of the season given a timestamp representing the start of a season.
    A season ends exactly 4 or 5 weeks after it started depending on the month.
    """
    four_weeks_later: datetime = season_start + timedelta(weeks=4)
    if four_weeks_later.month != season_start.month:
        return four_weeks_later
    return four_weeks_later + timedelta(weeks=1)


def get_time_since_last_clan_war_started(ts: datetime) -> timedelta:
    """
    Returns the timedelta since the start of the most recent clan war.
    Clan wars start roughly 10 AM UTC on Thursday.
    """
    days_since_last_thursday = (ts.weekday() - 3) % 7
    if days_since_last_thursday == 0 and ts.time() < time(hour=10):
        # the war beginning today has not yet started
        days_since_last_thursday = 7
    last_thursday = ts - timedelta(days=days_since_last_thursday)
    last_thursday_10am = datetime.combine(last_thursday, time(hour=10), ts.tzinfo)
    return ts - last_thursday_10am
