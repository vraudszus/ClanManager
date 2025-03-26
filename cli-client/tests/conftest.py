import pandas as pd
import pytest

from player_ranking.evaluation_performer import EvaluationPerformer
from player_ranking.models.clan import Clan
from player_ranking.models.ranking_parameters import (
    RankingParameters,
    RatingWeights,
    PromotionRequirements,
    Excuses,
    GoogleSheets,
)


@pytest.fixture
def ranking_parameters() -> RankingParameters:
    return RankingParameters(
        clanTag="#ABCDEF",
        ratingWeights=RatingWeights(
            ladder=0.075,
            warHistory=0.4,
            currentWar=0.25,
            previousSeasonLeague=0.0375,
            previousSeasonTrophies=0.0375,
            currentSeasonLeague=0.1,
            currentSeasonTrophies=0.1,
        ),
        newPlayerWarLogRating=500,
        promotionRequirements=PromotionRequirements(
            minFameForCountingWar=2700,
            minCountingWars=8,
        ),
        excuses=Excuses(
            notInClanExcuse="not in clan",
            newPlayerExcuse="new player",
            personalExcuse="excused",
        ),
        googleSheets=GoogleSheets(
            rating="rating",
            excuses="excuses",
        ),
        ratingFile="player-ranking.csv",
        ratingHistoryFile="player-ranking-history.csv",
        ratingHistoryImage="player-ranking-history.png",
        ignoreWars=[],
        threeDayWars=[],
    )


@pytest.fixture
def evaluation_performer(ranking_parameters: RankingParameters) -> EvaluationPerformer:
    return EvaluationPerformer(
        clan=Clan(),
        current_war=pd.Series(
            {
                "a": 100,
                "b": 200,
                "c": 0,
            }
        ),
        war_log=pd.DataFrame(
            {
                "a": {
                    "20.1": 300,
                    "20.0": 400,
                    "19.4": 500,
                },
                "b": {
                    "20.1": 200,
                    "19.4": 300,
                },
                "c": {},
            }
        ),
        ranking_parameters=ranking_parameters,
        excuses=pd.DataFrame(),
    )
