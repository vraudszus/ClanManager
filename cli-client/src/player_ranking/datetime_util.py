from datetime import date, datetime, time, timedelta, timezone


def get_previous_first_monday_10_AM(dt_utc: date) -> datetime:
    if dt_utc.weekday() >= dt_utc.day:
        # the current month didn't yet have a Monday
        prev_month_first_day: date = (dt_utc - timedelta(weeks=1)).replace(day=1)
        prev_first_monday: date = prev_month_first_day + timedelta(days=(7 - prev_month_first_day.weekday()) % 7)
    else:
        prev_month_first_day: date = dt_utc.replace(day=1)
        prev_first_monday: date = prev_month_first_day + timedelta(days=(7 - prev_month_first_day.weekday()) % 7)
    return datetime.combine(prev_first_monday, time(hour=10), timezone.utc)


def get_next_first_monday_10_AM(
    previous_first_monday_10_AM: datetime,
) -> datetime:
    # the next month's first Monday may be 4 or 5 weeks later
    four_weeks_later: datetime = previous_first_monday_10_AM + timedelta(weeks=4)
    if four_weeks_later.month != previous_first_monday_10_AM.month:
        return four_weeks_later
    return four_weeks_later + timedelta(weeks=1)


def get_time_since_last_thursday_10_Am(ts: datetime) -> timedelta:
    seconds_since_midnight = (ts - ts.replace(hour=10, minute=0, second=0, microsecond=0)).total_seconds()
    offset = (ts.weekday() - 3) % 7
    # Find datetime for last Thursday 10:00 am UTC (roughly the begin of the war days)
    begin_of_war_days = ts - timedelta(days=offset, seconds=seconds_since_midnight)
    return ts - begin_of_war_days
