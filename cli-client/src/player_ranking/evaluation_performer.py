import logging
from datetime import datetime, timedelta, timezone
from typing import List

import numpy as np
import pandas as pd

from player_ranking.models.clan import Clan
from player_ranking.datetime_util import (
    get_season_end,
    get_season_start,
    get_time_since_last_clan_war_started,
)
from player_ranking.excuse_acceptor import ExcuseAcceptor
from player_ranking.models.ranking_parameters import RankingParameters

LOGGER = logging.getLogger(__name__)
MAX_LEAGUE_NUMBER = 7


def normalize(val: int, max_val: int, min_val: int, default: int) -> float | None:
    if pd.isnull(val):
        return None
    if max_val == min_val:
        return default
    return (val - min_val) / (max_val - min_val) * 1000


class EvaluationPerformer:
    def __init__(
        self,
        clan: Clan,
        current_war: pd.Series,
        war_log: pd.DataFrame,
        ranking_parameters: RankingParameters,
        excuses: pd.DataFrame,
    ) -> None:
        self.clan: Clan = clan
        self.current_war = current_war
        self.war_log = war_log
        self.war_progress = None
        self.params = ranking_parameters
        self.excuses: pd.DataFrame = excuses

    def evaluate(self) -> pd.DataFrame:
        self.adjust_inputs()
        self.evaluate_ratings()
        return self.build_rating_df()

    def adjust_inputs(self) -> None:
        self.adjust_war_weights()
        self.adjust_season_weights()
        self.account_for_shorter_wars()
        self.ignore_selected_wars()
        ExcuseAcceptor(
            excuse_params=self.params.excuses,
            clan=self.clan,
            current_war=self.current_war,
            war_log=self.war_log,
            excuses=self.excuses,
            war_progress=self.war_progress,
        ).adjust_fame_with_excuses()

    def adjust_war_weights(self):
        weights = self.params.ratingWeights
        now = datetime.now(timezone.utc)
        time_since_start = get_time_since_last_clan_war_started(now)
        if time_since_start > timedelta(days=4):
            # Training days are currently happening, do not count current war
            war_progress = 0
            weights.warHistory += weights.currentWar
            weights.currentWar = 0
        else:
            # War days are currently happening
            # Linearly increase weight for current war
            war_progress = time_since_start / timedelta(days=4)  # ranges from 0 to 1
            weights.warHistory += weights.currentWar * (1 - war_progress)
            weights.currentWar *= war_progress

        LOGGER.info(f"War progress: {war_progress}")
        self.war_progress = war_progress
        weights.check()

    def adjust_season_weights(self) -> None:
        weights = self.params.ratingWeights
        now: datetime = datetime.now(timezone.utc)

        # the season ends at 10AM UTC on the first Monday of a month
        current_season_start: datetime = get_season_start(now)
        current_season_end: datetime = get_season_end(current_season_start)

        season_progress: float = (now - current_season_start) / (current_season_end - current_season_start)
        LOGGER.info(f"Season progress: {season_progress}")

        redistributed_season_weight = weights.currentSeasonLeague * season_progress
        weights.currentSeasonLeague -= redistributed_season_weight
        weights.previousSeasonLeague += redistributed_season_weight

        redistributed_trophy_weight = weights.currentSeasonTrophies * season_progress
        weights.currentSeasonTrophies -= redistributed_trophy_weight
        weights.previousSeasonTrophies += redistributed_trophy_weight
        weights.check()

    def ignore_selected_wars(self):
        ignored_wars: List[str] = self.params.ignoreWars
        ignored_wars_in_history = list(set(ignored_wars) & set(self.war_log.columns))
        self.war_log.loc[:, ignored_wars_in_history] = np.nan
        if ignored_wars and max([float(i) for i in ignored_wars]) > float(self.war_log.columns[0]):
            self.current_war.values[:] = 0

    def account_for_shorter_wars(self):
        shorter_wars_in_history = list(set(self.params.threeDayWars) & set(self.war_log.columns))
        self.war_log.loc[:, shorter_wars_in_history] *= 4 / 3

    def evaluate_ratings(self) -> None:
        weights = self.params.ratingWeights

        self.evaluate_war_log()
        self.evaluate_current_war()
        self.evaluate_previous_season()
        self.evaluate_current_season()
        self.evaluate_ladder()

        for player in self.clan.get_members():
            if player.war_history is None:
                war_history_rating = self.params.newPlayerWarLogRating
                LOGGER.info(f"Defaulted war log rating to {self.params.newPlayerWarLogRating} for {player.name}")
            else:
                war_history_rating = player.war_history

            player.rating = weights.ladder * player.ladder
            player.rating += weights.currentWar * player.current_war
            player.rating += weights.previousSeasonLeague * player.previous_league
            player.rating += weights.currentSeasonLeague * player.current_league
            player.rating += weights.previousSeasonTrophies * player.previous_trophies
            player.rating += weights.currentSeasonTrophies * player.current_trophies
            player.rating += weights.warHistory * war_history_rating

        LOGGER.info("Performance rating calculated according to the following formula:")
        LOGGER.info(
            "rating "
            f"= {weights.ladder:.2f}*ladder "
            f"+ {weights.currentWar:.2f}*currentWar "
            f"+ {weights.previousSeasonLeague:.2f}*previousLeague "
            f"+ {weights.currentSeasonLeague:.2f}*currentLeague "
            f"+ {weights.previousSeasonTrophies:.2f}*previousPathTrophies "
            f"+ {weights.currentSeasonTrophies:.2f}*currentPathTrophies "
            f"+ {weights.warHistory:.2f}*warHistory"
        )

    def evaluate_ladder(self) -> None:
        trophies_min = self.clan.get_min("trophies")
        trophies_max = self.clan.get_max("trophies")
        for player in self.clan.get_members():
            player.ladder = normalize(player.trophies, trophies_max, trophies_min, 1000)

    def evaluate_war_log(self) -> None:
        self.war_log["mean"] = self.war_log.mean(axis=1)
        war_log_max_fame = self.war_log["mean"].max()
        war_log_min_fame = self.war_log["mean"].min()
        for player in self.clan.get_members():
            player.avg_fame = self.war_log.at[player.tag, "mean"] if player.tag in self.war_log.index else None
            player.war_history = normalize(player.avg_fame, war_log_max_fame, war_log_min_fame, 1000)

    def evaluate_current_war(self) -> None:
        current_max_fame = self.current_war.max()
        current_min_fame = self.current_war.min()
        for player in self.clan.get_members():
            # player_tag is not present in current_war until a user has logged in after season reset
            current_fame = self.current_war[player.tag] if player.tag in self.current_war else 0
            player.current_war = normalize(current_fame, current_max_fame, current_min_fame, 1000)

    def evaluate_previous_season(self) -> None:
        previous_league_min = self.clan.get_min("previous_season_league_number")
        previous_league_max = self.clan.get_max("previous_season_league_number")

        # only count players in the highest league for trophy min, otherwise it will always be 0
        previous_trophies_min = self.clan.filter(
            lambda p: p.previous_season_league_number == MAX_LEAGUE_NUMBER
        ).get_min("previous_season_trophies")
        previous_trophies_max = self.clan.get_max("previous_season_trophies")

        for player in self.clan.get_members():
            previous_league = player.previous_season_league_number
            player.previous_league = normalize(previous_league, previous_league_max, previous_league_min, 1000)

            # only grant points to players in the highest league
            player.previous_trophies = 0
            if previous_league == MAX_LEAGUE_NUMBER:
                player.previous_trophies = normalize(
                    player.previous_season_trophies, previous_trophies_max, previous_trophies_min, 1000
                )

            # join path of legends related metric to reduce number of columns
            player.previous_season = player.previous_league + player.previous_trophies

    def evaluate_current_season(self) -> None:
        current_league_min = self.clan.get_min("current_season_league_number")
        current_league_max = self.clan.get_max("current_season_league_number")

        # only count players in the highest league for trophy min, otherwise it will always be 0
        current_trophies_min = self.clan.filter(lambda p: p.current_season_league_number == MAX_LEAGUE_NUMBER).get_min(
            "current_season_trophies"
        )
        current_trophies_max = self.clan.get_max("current_season_trophies")

        for player in self.clan.get_members():
            current_league = player.current_season_league_number
            player.current_league = normalize(current_league, current_league_max, current_league_min, 1000)

            # only grant points to players in the highest league
            player.current_trophies = 0
            if current_league == MAX_LEAGUE_NUMBER:
                player.current_trophies = normalize(
                    player.current_season_trophies, current_trophies_max, current_trophies_min, 1000
                )

            # join path of legends related metric to reduce number of columns
            player.current_season = player.current_league + player.current_trophies

    def build_rating_df(self) -> pd.DataFrame:
        rating = pd.DataFrame([player.__dict__ for player in self.clan.get_members()])
        rating = rating.set_index("tag")
        rating = rating[
            [
                "name",
                "rating",
                "ladder",
                "current_war",
                "war_history",
                "avg_fame",
                "current_season",
                "previous_season",
            ]
        ]
        return rating.sort_values("rating", ascending=False)
