from datetime import date, datetime, timedelta, timezone
from typing import Dict
import pandas as pd
import numpy as np
import math

from src.datetime_util import (
    get_next_first_monday_10_AM,
    get_previous_first_monday_10_AM,
    get_time_since_last_thursday_10_Am,
)


class EvaluationPerformer:
    def __init__(
        self,
        members: dict,
        currentWar: pd.Series,
        warLog: pd.DataFrame,
        path: pd.DataFrame,
        rating_coefficients: Dict[str, float],
    ) -> None:
        self.members = members
        self.currentWar = currentWar
        self.warLog = warLog
        self.path = path
        self.warProgress = None
        self.weights = rating_coefficients

    def adjust_war_weights(self):
        now = datetime.now(timezone.utc)
        time_since_start = get_time_since_last_thursday_10_Am(now)
        if time_since_start > timedelta(days=4):
            # Training days are currently happening, do not count current war
            war_progress = 0
            self.weights["warHistory"] += self.weights["currentWar"]
            self.weights["currentWar"] = 0
        else:
            # War days are currently happening
            # Linearly increase weight for current war
            war_progress = time_since_start / timedelta(days=4)  # ranges from 0 to 1
            self.weights["warHistory"] += self.weights["currentWar"] * (
                1 - war_progress
            )
            self.weights["currentWar"] *= war_progress

        print("War progress:", war_progress)
        self.warProgress = war_progress

    def adjust_season_weights(self) -> None:
        now: datetime = datetime.now(timezone.utc)
        today: date = now.date()

        # the season ends at 10AM UTC on the first Monday of a month
        current_season_start: datetime = get_previous_first_monday_10_AM(today)
        current_season_end: datetime = get_next_first_monday_10_AM(current_season_start)

        season_progress: float = (now - current_season_start) / (
            current_season_end - current_season_start
        )
        print(f"Season progress: {season_progress}")

        redistibuted_season_weight = (
            self.weights["currentSeasonLeague"] * season_progress
        )
        self.weights["currentSeasonLeague"] -= redistibuted_season_weight
        self.weights["previousSeasonLeague"] += redistibuted_season_weight

        redistibuted_trophy_weight = (
            self.weights["currentSeasonTrophies"] * season_progress
        )
        self.weights["currentSeasonTrophies"] -= redistibuted_trophy_weight
        self.weights["previousSeasonTrophies"] += redistibuted_trophy_weight

    def ignore_selected_wars(self, ignoreWars: list[str]):
        ignoredWarsInHistory = list(set(ignoreWars) & set(self.warLog.columns))
        self.warLog.loc[:, ignoredWarsInHistory] = np.nan
        if ignoreWars and max([float(i) for i in ignoreWars]) > float(
            self.warLog.columns[0]
        ):
            self.currentWar.values[:] = 0

    def account_for_shorter_wars(self, threeDayWars: list[str]):
        shorterWarsInHistory = list(set(threeDayWars) & set(self.warLog.columns))
        self.warLog.loc[:, shorterWarsInHistory] *= 4 / 3

    def accept_excuses(self, valid_excuses, excusesDf):
        def handle_war(tag, war, fame):
            excuse = excusesDf.at[tag, war]
            if not math.isnan(fame) and excuse in valid_excuses.values():
                if excuse in [
                    valid_excuses["notInClanExcuse"],
                    valid_excuses["newPlayerExcuse"],
                ]:
                    self.warLog.loc[tag, war] = np.nan
                else:
                    self.warLog.loc[tag, war] = 1600
                print("Excuse accepted for", war, excuse, self.members[tag]["name"])

        def handle_current_war(tag):
            excuse = excusesDf.at[tag, "current"]
            if excuse in valid_excuses.values():
                if excuse == valid_excuses["newPlayerExcuse"]:
                    self.currentWar.at[tag] = np.nan
                else:
                    self.currentWar.at[tag] = 1600 * self.warProgress
                print(
                    "Excuse accepted for current CW:", excuse, self.members[tag]["name"]
                )

        for tag in self.members:
            if tag in excusesDf.index:
                handle_current_war(tag)
                if tag in self.warLog.index:
                    for war, fame in self.warLog.loc[tag].items():
                        if war in excusesDf.columns:
                            handle_war(tag, war, fame)

    def evaluate_performance(self, new_player_warLog_rating):
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
            ladder_rating = (self.members[player_tag]["trophies"] - trophies_min) / (
                trophies_max - trophies_min
            )

            previous_league = self.path.at[player_tag, "previous_season_league_number"]
            previous_league_rating = (previous_league - previous_league_min) / (
                previous_league_max - previous_league_min
            )
            current_league = self.path.at[player_tag, "current_season_league_number"]
            current_league_rating = (current_league - current_league_min) / (
                current_league_max - current_league_min
            )

            # only grant points to players in league 10
            previous_trophies_rating = 0
            if previous_league == 10:
                previous_trophies_rating = (
                    self.path.at[player_tag, "previous_season_trophies"]
                    - previous_trophies_min
                ) / (previous_trophies_max - previous_trophies_min)
            current_trophies_rating = 0
            if current_league == 10:
                current_trophies_rating = (
                    self.path.at[player_tag, "current_season_trophies"]
                    - current_trophies_min
                ) / (current_thropies_max - current_trophies_min)

            warLog_mean = (
                self.warLog.at[player_tag, "mean"]
                if player_tag in self.warLog.index
                else None
            )

            if not pd.isnull(warLog_mean):
                warLog_rating = (warLog_mean - warLog_min_fame) / war_history_fame_range
            else:
                warLog_rating = None
            # player_tag is not present in current_war until a user has logged in after season reset
            current_fame = (
                self.currentWar[player_tag] if player_tag in self.currentWar else 0
            )
            if current_fame_range > 0:
                current_war_rating = (
                    current_fame - current_min_fame
                ) / current_fame_range
            else:
                # Default value that is used during trainings days.
                # Does not affect the rating on those days
                current_war_rating = 1

            self.members[player_tag]["rating"] = -1
            self.members[player_tag]["ladder"] = ladder_rating * 1000
            self.members[player_tag]["current_war"] = current_war_rating * 1000
            self.members[player_tag]["war_history"] = (
                warLog_rating * 1000 if warLog_rating is not None else None
            )
            self.members[player_tag]["avg_fame"] = (
                self.warLog.at[player_tag, "mean"]
                if player_tag in self.warLog.index
                else None
            )
            self.members[player_tag]["previous_league"] = previous_league_rating * 1000
            self.members[player_tag]["current_league"] = current_league_rating * 1000
            self.members[player_tag]["previous_trophies"] = (
                previous_trophies_rating * 1000
            )
            self.members[player_tag]["current_trophies"] = (
                current_trophies_rating * 1000
            )

            self.members[player_tag]["current_season"] = (
                self.members[player_tag]["current_league"]
                + self.members[player_tag]["current_trophies"]
            )
            self.members[player_tag]["previous_season"] = (
                self.members[player_tag]["previous_league"]
                + self.members[player_tag]["previous_trophies"]
            )

            self.members[player_tag]["rating"] = (
                self.weights["ladder"] * self.members[player_tag]["ladder"]
                + self.weights["currentWar"] * self.members[player_tag]["current_war"]
                + self.weights["previousSeasonLeague"]
                * self.members[player_tag]["previous_league"]
                + self.weights["currentSeasonLeague"]
                * self.members[player_tag]["current_league"]
                + self.weights["previousSeasonTrophies"]
                * self.members[player_tag]["previous_trophies"]
                + self.weights["currentSeasonTrophies"]
                * self.members[player_tag]["current_trophies"]
            )
            if self.members[player_tag]["war_history"] is not None:
                self.members[player_tag]["rating"] += (
                    self.weights["warHistory"] * self.members[player_tag]["war_history"]
                )
            else:
                self.members[player_tag]["rating"] += (
                    self.weights["warHistory"] * new_player_warLog_rating
                )

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

        print("Performance rating calculated according to the following formula:")
        print(
            "rating =",
            "{:.2f}".format(self.weights["ladder"]),
            "* ladder +",
            "{:.2f}".format(self.weights["currentWar"]),
            "* current_war +",
            "{:.2f}".format(self.weights["warHistory"]),
            "* war_history",
        )
        return performance.sort_values("rating", ascending=False)
