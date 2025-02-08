import logging
from datetime import date, datetime, timedelta, timezone
from typing import List

import numpy as np
import pandas as pd

from player_ranking.models.clan import Clan
from player_ranking.datetime_util import (
    get_next_first_monday_10_AM,
    get_previous_first_monday_10_AM,
    get_time_since_last_thursday_10_Am,
)
from player_ranking.excuse_acceptor import ExcuseAcceptor
from player_ranking.models.ranking_parameters import RankingParameters

LOGGER = logging.getLogger(__name__)


def normalize(val: int, max_val: int, min_val: int, default: int) -> float:
    if max_val == min_val:
        return default
    return (val - min_val) / (max_val - min_val)


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
        ).update_fame_with_excuses()
        return self.evaluate_performance()

    def adjust_war_weights(self):
        weights = self.params.ratingWeights
        now = datetime.now(timezone.utc)
        time_since_start = get_time_since_last_thursday_10_Am(now)
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
        today: date = now.date()

        # the season ends at 10AM UTC on the first Monday of a month
        current_season_start: datetime = get_previous_first_monday_10_AM(today)
        current_season_end: datetime = get_next_first_monday_10_AM(current_season_start)

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

    def evaluate_performance(self):
        weights = self.params.ratingWeights
        self.war_log["mean"] = self.war_log.mean(axis=1)
        war_log_max_fame = self.war_log["mean"].max()
        war_log_min_fame = self.war_log["mean"].min()
        current_max_fame = self.current_war.max()
        current_min_fame = self.current_war.min()

        previous_league_min = self.clan.get_min("previous_season_league_number")
        previous_league_max = self.clan.get_max("previous_season_league_number")
        current_league_min = self.clan.get_min("current_season_league_number")
        current_league_max = self.clan.get_max("current_season_league_number")

        # only count league 10 players for trophy min, otherwise it will always be 0
        previous_trophies_min = self.clan.filter(lambda p: p.previous_season_league_number == 10).get_min(
            "previous_season_trophies"
        )
        previous_trophies_max = self.clan.get_max("previous_season_trophies")
        current_trophies_min = self.clan.filter(lambda p: p.current_season_league_number == 10).get_min(
            "current_season_trophies"
        )
        current_trophies_max = self.clan.get_max("current_season_trophies")

        trophies_min = self.clan.get_min("trophies")
        trophies_max = self.clan.get_max("trophies")

        for player in self.clan.get_members():
            ladder_rating = normalize(player.trophies, trophies_max, trophies_min, 1)

            previous_league = player.previous_season_league_number
            previous_league_rating = normalize(previous_league, previous_league_max, previous_league_min, 1)
            current_league = player.current_season_league_number
            current_league_rating = normalize(current_league, current_league_max, current_league_min, 1)

            # only grant points to players in league 10
            previous_trophies_rating = 0
            if previous_league == 10:
                previous_trophies_rating = normalize(
                    player.previous_season_trophies, previous_trophies_max, previous_trophies_min, 1
                )
            current_trophies_rating = 0
            if current_league == 10:
                current_trophies_rating = normalize(
                    player.current_season_trophies, current_trophies_max, current_trophies_min, 1
                )

            war_log_mean = self.war_log.at[player.tag, "mean"] if player.tag in self.war_log.index else None
            if not pd.isnull(war_log_mean):
                war_log_rating = normalize(war_log_mean, war_log_max_fame, war_log_min_fame, 1)
            else:
                war_log_rating = None

            # player_tag is not present in current_war until a user has logged in after season reset
            current_fame = self.current_war[player.tag] if player.tag in self.current_war else 0
            current_war_rating = normalize(current_fame, current_max_fame, current_min_fame, 1)

            player.ladder = ladder_rating * 1000
            player.current_war = current_war_rating * 1000
            player.war_history = war_log_rating * 1000 if war_log_rating is not None else None
            player.avg_fame = war_log_mean
            player.previous_league = previous_league_rating * 1000
            player.current_league = current_league_rating * 1000
            player.previous_trophies = previous_trophies_rating * 1000
            player.current_trophies = current_trophies_rating * 1000

            player.current_season = player.current_league + player.current_trophies
            player.previous_season = player.previous_league + player.previous_trophies

            war_history_rating = self.params.newPlayerWarLogRating if player.war_history is None else player.war_history
            player.rating = (
                weights.ladder * player.ladder
                + weights.currentWar * player.current_war
                + weights.previousSeasonLeague * player.previous_league
                + weights.currentSeasonLeague * player.current_league
                + weights.previousSeasonTrophies * player.previous_trophies
                + weights.currentSeasonTrophies * player.current_trophies
                + weights.warHistory * war_history_rating
            )

        performance = pd.DataFrame([player.__dict__ for player in self.clan.get_members()])
        performance = performance.set_index("tag")
        performance = performance[
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
        return performance.sort_values("rating", ascending=False)
