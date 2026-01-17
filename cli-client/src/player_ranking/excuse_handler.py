import logging
import math

import numpy as np
import pandas as pd

from player_ranking.models.clan import Clan
from player_ranking.models.ranking_parameters import Excuses


LOGGER = logging.getLogger(__name__)


class ExcuseHandler:
    def __init__(
        self,
        excuses: pd.DataFrame,
        clan: Clan,
        excuse_params: Excuses,
    ):
        self._excuses: pd.DataFrame = excuses
        self._clan: Clan = clan
        self._params: Excuses = excuse_params

    def get_excuses_as_df(self) -> pd.DataFrame:
        return self._excuses

    def update_excuses(self, current_war: pd.Series, war_log: pd.DataFrame) -> None:
        updated_excuses: pd.DataFrame = self._excuses.copy()

        updated_excuses = self.add_missing_wars(excuses=updated_excuses, current_war=current_war, wars=war_log)
        self.add_missing_players(excuses=updated_excuses, clan=self._clan)
        self.update_current_war(
            excuses=updated_excuses,
            clan=self._clan,
            current_war=current_war,
            not_in_clan_excuse=self._params.notInClanExcuse,
        )
        self.truncate(excuses=updated_excuses, not_in_clan_excuse=self._params.notInClanExcuse)
        self.format(excuses=updated_excuses)

        self._excuses = updated_excuses

    def adjust_fame_with_excuses(self, current_war: pd.Series, war_log: pd.DataFrame, war_progress: float) -> None:
        for player in self._clan.get_members():
            # current river race
            current_war.at[player.tag] = self.get_new_fame(
                excuse_params=self._params,
                player_name=player.name,
                excuse=self._excuses.at[player.tag, current_war.name],
                old_fame=current_war.get(player.tag, 0),
                war_id=str(current_war.name),
                factor=war_progress,
            )
            if player.tag in war_log.index:
                for war, fame in war_log.loc[player.tag].items():
                    # river race history
                    war_log.loc[player.tag, war] = self.get_new_fame(
                        excuse_params=self._params,
                        player_name=player.name,
                        excuse=self._excuses.at[player.tag, war],
                        old_fame=fame,
                        war_id=war,
                    )

    @staticmethod
    def add_missing_wars(excuses: pd.DataFrame, current_war: pd.Series, wars: pd.DataFrame) -> pd.DataFrame:
        if excuses.columns.empty:
            excuses["name"] = ""

        all_wars = [current_war.name] + wars.columns.tolist()
        for war in all_wars:
            if war not in excuses.columns:
                excuses[war] = ""

        name_col = excuses.columns[0]
        war_cols = excuses.columns[1:]
        # sort wars by their "seasonId.sectionIndex" (requires current_war series to be properly named)
        sorted_cols = [name_col] + sorted(war_cols, key=lambda x: float(x), reverse=True)
        return excuses[sorted_cols]

    @staticmethod
    def add_missing_players(excuses: pd.DataFrame, clan: Clan) -> None:
        for player in clan.get_members():
            if player.tag not in excuses.index:
                excuses.loc[player.tag] = ""
            excuses.loc[player.tag, "name"] = player.name

    @staticmethod
    def update_current_war(excuses: pd.DataFrame, clan: Clan, current_war: pd.Series, not_in_clan_excuse: str) -> None:
        current_war_label = current_war.name
        current_war_excuses = excuses[current_war_label]
        for tag, excuse in current_war_excuses.items():
            if excuse == not_in_clan_excuse and tag in clan:
                LOGGER.info(f"Unsetting excuse {not_in_clan_excuse} for player {tag} as player is in clan.")
                excuses.loc[tag, current_war_label] = ""
            if tag not in clan and (excuse is None or excuse == "") and excuse != not_in_clan_excuse:
                excuses.loc[tag, current_war_label] = not_in_clan_excuse
                LOGGER.info(f"Setting excuse {not_in_clan_excuse} for player {tag} as player is not in clan.")

    @staticmethod
    def truncate(excuses: pd.DataFrame, not_in_clan_excuse: str) -> None:
        """
        Only retain data for the current and the previous 10 river races.
        Removes players that weren't in the clan during this window.
        """
        tags_to_remove = excuses[excuses.eq(not_in_clan_excuse).sum(1) >= 11].index
        if not tags_to_remove.empty:
            LOGGER.info(
                f"Drop rows for tags {tags_to_remove.tolist()} from excuses "
                f"as players haven't been in the clan in a long time."
            )
            excuses.drop(tags_to_remove, inplace=True)

        # 12 columns: name + current war + 10 completed wars
        columns_to_drop = excuses.columns[12:]
        if not columns_to_drop.empty:
            LOGGER.info(f"Drop columns {columns_to_drop.tolist()} from excuses as wars are too old.")
            excuses.drop(columns_to_drop, axis=1, inplace=True)

    @staticmethod
    def format(excuses: pd.DataFrame) -> None:
        excuses.index.name = "tag"
        excuses.sort_values(by="name", inplace=True)

    @staticmethod
    def get_new_fame(
        excuse_params: Excuses, player_name: str, excuse: str, old_fame: int | float, war_id: str, factor: float = 1
    ) -> int:
        if not excuse or math.isnan(old_fame):
            # no excuse found or player did not participate
            return old_fame
        excuse_params.check_excuse(excuse)
        if excuse_params.should_ignore_war(excuse):
            new_fame = np.nan
        else:
            # scale if race is still ongoing
            new_fame = int(1600 * factor)
        LOGGER.info(f"Excuse {excuse} accepted for player={player_name} in war={war_id}")
        return new_fame
