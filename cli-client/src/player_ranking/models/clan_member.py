from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
    rating: float = Optional[float]
    ladder: float = Optional[float]
    current_war: float = Optional[float]
    war_history: float = Optional[float]
    previous_league: float = Optional[float]
    current_league: float = Optional[float]
    previous_trophies: float = Optional[float]
    current_trophies: float = Optional[float]
    current_season: float = Optional[float]
    previous_season: float = Optional[float]

    # player stats
    avg_fame: float = Optional[float]
    current_season_league_number: int = Optional[int]
    previous_season_league_number: int = Optional[int]
    current_season_trophies: int = Optional[int]
    previous_season_trophies: int = Optional[int]

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
