from dataclasses import dataclass
from datetime import datetime


@dataclass
class ClanMember:
    # basic stats
    tag: str
    name: str
    role: str
    trophies: int
    level: int
    net_donations: int
    last_seen: datetime

    # ratings
    rating: float | None = None
    ladder: float | None = None
    current_war: float | None = None
    war_history: float | None = None
    previous_league: float | None = None
    current_league: float | None = None
    previous_trophies: float | None = None
    current_trophies: float | None = None
    current_season: float | None = None
    previous_season: float | None = None

    # player stats
    avg_fame: float | None = None
    current_season_league_number: int | None = None
    previous_season_league_number: int | None = None
    current_season_trophies: int | None = None
    previous_season_trophies: int | None = None

    def __init__(
        self,
        tag: str,
        name: str,
        role: str,
        trophies: int,
        level: int,
        net_donations: int,
        last_seen: datetime,
    ):
        self.tag: str = tag
        self.name: str = name
        self.role: str = role
        self.trophies: int = trophies
        self.level: int = level
        self.net_donations: int = net_donations
        self.last_seen: datetime = last_seen
