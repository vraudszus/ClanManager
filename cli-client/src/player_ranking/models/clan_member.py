from dataclasses import dataclass
from typing import Optional


@dataclass
class ClanMember:
    # basic stats
    tag: str
    name: str
    role: str
    trophies: int

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

    def __init__(self, tag: str, name: str, role: str, trophies: int):
        self.tag: str = tag
        self.name: str = name
        self.role: str = role
        self.trophies: int = trophies
