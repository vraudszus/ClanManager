import math
from dataclasses import dataclass, field, is_dataclass
from typing import List


def nested_dataclass(*args, **kwargs):
    """Solves issue of dataclass typed fields will be assigned dicts instead of dataclass objects."""

    def wrapper(cls):
        cls = dataclass(cls, **kwargs)
        original_init = cls.__init__

        def __init__(self, *args, **kwargs):
            for name, value in kwargs.items():
                field_type = cls.__annotations__.get(name, None)
                if is_dataclass(field_type) and isinstance(value, dict):
                    new_obj = field_type(**value)
                    kwargs[name] = new_obj
            original_init(self, *args, **kwargs)

        cls.__init__ = __init__
        return cls

    return wrapper(args[0]) if args else wrapper


@dataclass
class RatingWeights:
    ladder: float
    warHistory: float
    currentWar: float
    previousSeasonLeague: float
    previousSeasonTrophies: float
    currentSeasonLeague: float
    currentSeasonTrophies: float

    def check(self) -> None:
        weights = [value for value in self.__dict__.values()]
        if min(weights) < 0:
            raise ValueError("All ratingWeights must be positive.")
        if not math.isclose(sum(weights), 1):
            raise ValueError("Sum of ratingWeights must be 1.")


@dataclass
class PromotionRequirements:
    minFameForCountingWar: int
    minCountingWars: int


@dataclass
class Excuses:
    notInClanExcuse: str
    newPlayerExcuse: str
    personalExcuse: str

    def check_excuse(self, excuse: str):
        if excuse not in [v for v in self.__dict__.values()]:
            raise ValueError(f"Unknown excuse '{excuse}' encountered.")

    def should_ignore_war(self, excuse: str):
        return excuse == self.notInClanExcuse or excuse == self.newPlayerExcuse


@dataclass
class GoogleSheets:
    rating: str
    excuses: str


@nested_dataclass
class RankingParameters:
    clanTag: str
    ratingWeights: RatingWeights
    newPlayerWarLogRating: int
    promotionRequirements: PromotionRequirements
    excuses: Excuses
    googleSheets: GoogleSheets
    ratingFile: str
    ratingHistoryFile: str
    ratingHistoryImage: str
    ignoreWars: List[str] = field(default_factory=list)
    threeDayWars: List[str] = field(default_factory=list)
