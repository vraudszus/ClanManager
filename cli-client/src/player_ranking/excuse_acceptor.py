import logging
import math

import numpy as np
import pandas as pd

from player_ranking.clan import Clan
from player_ranking.ranking_parameters import Excuses

LOGGER = logging.getLogger(__name__)


class ExcuseAcceptor:
    def __init__(
        self,
        excuse_params: Excuses,
        clan: Clan,
        current_war: pd.Series,
        war_log: pd.DataFrame,
        excuses: pd.DataFrame,
        war_progress: float,
    ):
        self.excuse_params: Excuses = excuse_params
        self.clan: Clan = clan
        self.current_war: pd.Series = current_war
        self.war_log: pd.DataFrame = war_log
        self.excuses: pd.DataFrame = excuses
        self.war_progress = war_progress

    def update_fame_with_excuses(self) -> None:
        for tag in self.clan.get_tags():
            if tag in self.excuses.index:
                # current river race
                self.current_war.at[tag] = self.get_new_fame(
                    player_tag=tag,
                    old_fame=self.current_war.at[tag],
                    war_id="current",
                    factor=self.war_progress,
                )
                if tag in self.war_log.index:
                    for war, fame in self.war_log.loc[tag].items():
                        if war in self.excuses.columns:
                            # river race history
                            self.war_log.loc[tag, war] = self.get_new_fame(
                                player_tag=tag,
                                old_fame=fame,
                                war_id=war,
                            )

    def get_new_fame(self, player_tag: str, old_fame: int, war_id: str, factor: float = 1) -> int:
        excuse = self.excuses.at[player_tag, war_id]
        player_name = self.clan.get(player_tag).name
        if not excuse or math.isnan(old_fame):
            return old_fame
        self.excuse_params.check_excuse(excuse)
        if self.excuse_params.should_ignore_war(excuse):
            new_fame = np.nan
        else:
            # scale if race is still ongoing
            new_fame = int(1600 * factor)
        LOGGER.info(f"Excuse {excuse} accepted for player={player_name} in war={war_id}")
        return new_fame
