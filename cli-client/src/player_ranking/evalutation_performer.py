import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import List

import numpy as np
import pandas as pd

from player_ranking.datetime_util import (
    get_next_first_monday_10_AM,
    get_previous_first_monday_10_AM,
    get_time_since_last_thursday_10_Am,
)
from player_ranking.ranking_parameters import RankingParameters

LOGGER = logging.getLogger(__name__)


class EvaluationPerformer:
    def __init__(
        self,
        members: dict,
        currentWar: pd.Series,
        warLog: pd.DataFrame,
        path: pd.DataFrame,
        ranking_parameters: RankingParameters,
    ) -> None:
        self.members = members
        self.currentWar = currentWar
        self.warLog = warLog
        self.path = path
        self.warProgress = None
        self.params = ranking_parameters

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
        self.warProgress = war_progress
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
        ignoredWarsInHistory = list(set(ignored_wars) & set(self.warLog.columns))
        self.warLog.loc[:, ignoredWarsInHistory] = np.nan
        if ignored_wars and max([float(i) for i in ignored_wars]) > float(self.warLog.columns[0]):
            self.currentWar.values[:] = 0

    def account_for_shorter_wars(self):
        shorterWarsInHistory = list(set(self.params.threeDayWars) & set(self.warLog.columns))
        self.warLog.loc[:, shorterWarsInHistory] *= 4 / 3

    def accept_excuses(self, excuses_df):
        def handle_excuse(player_name: str, old_fame: int, war_id: str, factor: float = 1):
            excuse = excuses_df.at[tag, war_id]
            if not excuse or math.isnan(old_fame):
                return old_fame
            self.params.excuses.check_excuse(excuse)
            if self.params.excuses.should_ignore_war(excuse):
                new_fame = np.nan
            else:
                # scale if race is still ongoing
                new_fame = int(1600 * factor)
            LOGGER.info(f"Excuse {excuse} accepted for player={player_name} in war={war_id}")
            return new_fame

        for tag in self.members:
            name = self.members[tag]["name"]
            if tag in excuses_df.index:
                # current river race
                self.currentWar.at[tag] = handle_excuse(
                    player_name=name,
                    old_fame=self.currentWar.at[tag],
                    war_id="current",
                    factor=self.warProgress,
                )
                if tag in self.warLog.index:
                    for war, fame in self.warLog.loc[tag].items():
                        if war in excuses_df.columns:
                            # river race history
                            self.warLog.loc[tag, war] = handle_excuse(
                                player_name=name,
                                old_fame=fame,
                                war_id=war,
                            )

    def evaluate_performance(self):
        weights = self.params.ratingWeights
        self.warLog["mean"] = self.warLog.mean(axis=1)
        warLog_max_fame = self.warLog["mean"].max()
        warLog_min_fame = self.warLog["mean"].min()
        war_history_fame_range = warLog_max_fame - warLog_min_fame
        current_max_fame = self.currentWar.max()
        current_min_fame = self.currentWar.min()
        current_fame_range = current_max_fame - current_min_fame

        previous_league_min = self.path["previous_season_league_number"].min()
        previous_league_max = self.path["previous_season_league_number"].max()
        current_league_min = self.path["current_season_league_number"].min()
        current_league_max = self.path["current_season_league_number"].max()

        # only count league 10 players for throphy min, otherwise it will always be 0
        previous_trophies_min = self.path.loc[
            self.path["previous_season_league_number"] == 10, "previous_season_trophies"
        ].min()
        previous_trophies_max = self.path["previous_season_trophies"].max()
        current_trophies_min = self.path.loc[
            self.path["current_season_league_number"] == 10, "current_season_trophies"
        ].min()
        current_thropies_max = self.path["current_season_trophies"].max()

        members_df = pd.DataFrame.from_dict(self.members, orient="index")
        trophies_min = members_df["trophies"].min()
        trophies_max = members_df["trophies"].max()

        for player_tag in self.members.keys():
            ladder_rating = (
                (self.members[player_tag]["trophies"] - trophies_min) / (trophies_max - trophies_min)
                if trophies_max != trophies_min
                else 1
            )

            previous_league = self.path.at[player_tag, "previous_season_league_number"]
            previous_league_rating = (
                (previous_league - previous_league_min) / (previous_league_max - previous_league_min)
                if previous_league_max != previous_league_min
                else 1
            )
            current_league = self.path.at[player_tag, "current_season_league_number"]
            current_league_rating = (
                (current_league - current_league_min) / (current_league_max - current_league_min)
                if current_league_max != current_league_min
                else 1
            )

            # only grant points to players in league 10
            previous_trophies_rating = 0
            if previous_league == 10:
                previous_trophies_rating = (
                    (self.path.at[player_tag, "previous_season_trophies"] - previous_trophies_min)
                    / (previous_trophies_max - previous_trophies_min)
                    if previous_trophies_max != previous_trophies_min
                    else 1
                )
            current_trophies_rating = 0
            if current_league == 10:
                current_trophies_rating = (
                    (self.path.at[player_tag, "current_season_trophies"] - current_trophies_min)
                    / (current_thropies_max - current_trophies_min)
                    if current_thropies_max != current_trophies_min
                    else 1
                )

            warLog_mean = self.warLog.at[player_tag, "mean"] if player_tag in self.warLog.index else None

            if not pd.isnull(warLog_mean):
                warLog_rating = (
                    (warLog_mean - warLog_min_fame) / war_history_fame_range if war_history_fame_range != 0 else 1
                )
            else:
                warLog_rating = None
            # player_tag is not present in current_war until a user has logged in after season reset
            current_fame = self.currentWar[player_tag] if player_tag in self.currentWar else 0
            if current_fame_range > 0:
                current_war_rating = (
                    (current_fame - current_min_fame) / current_fame_range if current_fame_range != 0 else 1
                )
            else:
                # Default value that is used during trainings days.
                # Does not affect the rating on those days
                current_war_rating = 1

            self.members[player_tag]["rating"] = -1
            self.members[player_tag]["ladder"] = ladder_rating * 1000
            self.members[player_tag]["current_war"] = current_war_rating * 1000
            self.members[player_tag]["war_history"] = warLog_rating * 1000 if warLog_rating is not None else None
            self.members[player_tag]["avg_fame"] = (
                self.warLog.at[player_tag, "mean"] if player_tag in self.warLog.index else None
            )
            self.members[player_tag]["previous_league"] = previous_league_rating * 1000
            self.members[player_tag]["current_league"] = current_league_rating * 1000
            self.members[player_tag]["previous_trophies"] = previous_trophies_rating * 1000
            self.members[player_tag]["current_trophies"] = current_trophies_rating * 1000

            self.members[player_tag]["current_season"] = (
                self.members[player_tag]["current_league"] + self.members[player_tag]["current_trophies"]
            )
            self.members[player_tag]["previous_season"] = (
                self.members[player_tag]["previous_league"] + self.members[player_tag]["previous_trophies"]
            )

            self.members[player_tag]["rating"] = (
                weights.ladder * self.members[player_tag]["ladder"]
                + weights.currentWar * self.members[player_tag]["current_war"]
                + weights.previousSeasonLeague * self.members[player_tag]["previous_league"]
                + weights.currentSeasonLeague * self.members[player_tag]["current_league"]
                + weights.previousSeasonTrophies * self.members[player_tag]["previous_trophies"]
                + weights.currentSeasonTrophies * self.members[player_tag]["current_trophies"]
            )
            if self.members[player_tag]["war_history"] is not None:
                self.members[player_tag]["rating"] += weights.warHistory * self.members[player_tag]["war_history"]
            else:
                self.members[player_tag]["rating"] += weights.warHistory * self.params.newPlayerWarLogRating

        performance = pd.DataFrame.from_dict(self.members, orient="index")
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
