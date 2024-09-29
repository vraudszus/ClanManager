from dataclasses import dataclass, field
from typing import List


@dataclass
class RatingWeights:
    ladder: float
    warHistory: float
    currentWar: float
    previousSeasonLeague: float
    previousSeasonTrophies: float
    currentSeasonLeague: float
    currentSeasonTrophies: float

    def sum_of_weights(self):
        return sum(value for value in self.__dict__.values())


@dataclass
class PromotionDemotionRequirements:
    minFameForCountingWar: int
    minCountingWars: int


@dataclass
class Excuses:
    notInClanExcuse: str
    newPlayerExcuse: str
    personalExcuse: str


@dataclass
class GoogleSheets:
    rating: str
    excuses: str


@dataclass
class RankingParameters:
    clanTag: str
    ratingWeights: RatingWeights
    newPlayerWarLogRating: int
    promotionDemotionRequirements: PromotionDemotionRequirements
    excuses: Excuses
    googleSheets: GoogleSheets
    ratingFile: str
    ratingHistoryFile: str
    ratingHistoryImage: str
    ignoreWars: List[str] = field(default_factory=list)
    threeDayWars: List[str] = field(default_factory=list)
