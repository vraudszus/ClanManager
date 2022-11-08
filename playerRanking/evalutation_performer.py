import pandas as pd
import datetime
import numpy as np
import math


class EvaluationPerformer:

    def __init__(self, members: dict, currentWar: pd.Series, warLog: pd.DataFrame) -> None:
        self.members = members
        self.currentWar = currentWar
        self.warLog = warLog
        self.warProgress = None
        self.ratingCoefficients = None

    def adjust_war_weights(self, rating_coefficients):
        now = datetime.datetime.utcnow()
        seconds_since_midnight = (
            now - now.replace(hour=10, minute=0, second=0, microsecond=0)).total_seconds()
        offset = (now.weekday() - 3) % 7
        # Find datetime for last Thursday 10:00 am UTC (roughly the begin of the war days)
        begin_of_war_days = now - \
            datetime.timedelta(days=offset, seconds=seconds_since_midnight)
        time_since_start = now - begin_of_war_days
        if time_since_start > datetime.timedelta(days=4):
            # Training days are currently happening, do not count current war
            war_progress = 0
            rating_coefficients["warHistory"] += rating_coefficients["currentWar"]
            rating_coefficients["currentWar"] = 0
        else:
            # War days are currently happening
            # Linearly increase weight for current war
            war_progress = time_since_start / \
                datetime.timedelta(days=4)  # ranges from 0 to 1
            rating_coefficients["warHistory"] += (
                rating_coefficients["currentWar"] * (1 - war_progress))
            rating_coefficients["currentWar"] *= war_progress

        print("War progress:", war_progress)
        self.warProgress = war_progress
        self.ratingCoefficients = rating_coefficients

    def ignore_selected_wars(self, ignoreWars: list[str]):
        ignoredWarsInHistory = list(set(ignoreWars) & set(self.warLog.columns))
        self.warLog.loc[:, ignoredWarsInHistory] = np.nan
        if ignoreWars and max([float(i) for i in ignoreWars]) > float(self.warLog.columns[0]):
            self.currentWar.values[:] = 0

    def account_for_shorter_wars(self, threeDayWars: list[str]):
        shorterWarsInHistory = list(set(threeDayWars) & set(self.warLog.columns))
        self.warLog.loc[:, shorterWarsInHistory] *= 4 / 3

    def accept_excuses(self, valid_excuses, excusesDf):

        def handle_war(tag, war, fame):
            excuse = excusesDf.at[tag, war]
            if not math.isnan(fame) and excuse in valid_excuses.values():
                if excuse in [valid_excuses["notInClanExcuse"], valid_excuses["newPlayerExcuse"]]:
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
                print("Excuse accepted for current CW:", excuse, self.members[tag]["name"])

        for tag in self.members:
            if tag in excusesDf.index:
                handle_current_war(tag)
                if tag in self.warLog.index:
                    for war, fame in self.warLog.loc[tag].items():
                        if war in excusesDf.columns:
                            handle_war(tag, war, fame)

    def evaluate_performance(self, new_player_warLog_rating):
        max_trophies = max([info["trophies"] for _, info in self.members.items()])
        min_trophies = min([info["trophies"] for _, info in self.members.items()])
        trophy_range = max_trophies - min_trophies
        self.warLog["mean"] = self.warLog.mean(axis=1)
        warLog_max_fame = self.warLog["mean"].max()
        warLog_min_fame = self.warLog["mean"].min()
        war_history_fame_range = warLog_max_fame - warLog_min_fame
        current_max_fame = self.currentWar.max()
        current_min_fame = self.currentWar.min()
        current_fame_range = current_max_fame - current_min_fame

        for player_tag in self.members.keys():
            trophies = self.members[player_tag]["trophies"]
            ladder_rating = ((trophies - min_trophies) / trophy_range)
            warLog_mean = (self.warLog.at[player_tag, "mean"]
                           if player_tag in self.warLog.index else None)

            if not pd.isnull(warLog_mean):
                warLog_rating = (warLog_mean - warLog_min_fame) / war_history_fame_range
            else:
                warLog_rating = None
            # player_tag is not present in current_war until a user has logged in after season reset
            current_fame = self.currentWar[player_tag] if player_tag in self.currentWar else 0
            if current_fame_range > 0:
                current_war_rating = (
                    current_fame - current_min_fame) / current_fame_range
            else:
                # Default value that is used during trainings days.
                # Does not affect the rating on those days
                current_war_rating = 1

            self.members[player_tag]["rating"] = -1
            self.members[player_tag]["ladder"] = ladder_rating * 1000
            self.members[player_tag]["current_war"] = current_war_rating * 1000
            self.members[player_tag]["war_history"] = (warLog_rating * 1000
                                                       if warLog_rating is not None else None)
            self.members[player_tag]["avg_fame"] = (self.warLog.at[player_tag, "mean"]
                                                    if player_tag in self.warLog.index else None)

            self.members[player_tag]["rating"] = (self.ratingCoefficients["ladder"]
                                                  * self.members[player_tag]["ladder"]
                                                  + self.ratingCoefficients["currentWar"]
                                                  * self.members[player_tag]["current_war"])
            if self.members[player_tag]["war_history"] is not None:
                self.members[player_tag]["rating"] += (self.ratingCoefficients["warHistory"]
                                                       * self.members[player_tag]["war_history"])
            else:
                self.members[player_tag]["rating"] += (self.ratingCoefficients["warHistory"]
                                                       * new_player_warLog_rating)

        performance = pd.DataFrame.from_dict(self.members, orient="index")
        performance = performance[["name", "rating", "ladder", "current_war",
                                   "war_history", "avg_fame", "ladderRank"]]

        print("Performance rating calculated according to the following formula:")
        print("rating =",
              "{:.2f}".format(self.ratingCoefficients["ladder"]), "* ladder +",
              "{:.2f}".format(self.ratingCoefficients["currentWar"]), "* current_war +",
              "{:.2f}".format(self.ratingCoefficients["warHistory"]), "* war_history")
        return performance.sort_values("rating", ascending=False)
