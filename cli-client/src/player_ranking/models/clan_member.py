from dataclasses import dataclass


@dataclass
class ClanMember:
    # ratings
    rating: float
    ladder: float
    current_war: float
    war_history: float
    previous_league: float
    current_league: float
    previous_trophies: float
    current_trophies: float
    current_season: float
    previous_season: float

    # player stats
    avg_fame: float
    current_season_league_number: int
    previous_season_league_number: int
    current_season_trophies: int
    previous_season_trophies: int

    def __init__(self, tag: str, name: str, role: str, trophies: int):
        self.tag: str = tag
        self.name: str = name
        self.role: str = role
        self.trophies: int = trophies
