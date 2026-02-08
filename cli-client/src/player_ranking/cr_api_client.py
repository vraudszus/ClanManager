import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
import pandas as pd

from player_ranking.datetime_util import parse_timestamp
from player_ranking.models.clan import Clan
from player_ranking.models.clan_member import ClanMember

# URL of the proxy provided by RoyaleAPI.com
# Alternatively you can use the official URL "https://api.clashroyale.com/v1"
# Dynamic IPs don't work with the official URL as the IP must be whitelisted
API_ENDPOINT: str = "https://proxy.royaleapi.dev/v1"
LOGGER = logging.getLogger(__name__)


def url_encode(tag: str) -> str:
    return f"%23{tag[1:]}"


class CRAPIClient:
    def __init__(self, api_token: str, clan_tag: str):
        self.api_token: str = api_token
        self.clan_tag: str = clan_tag

    def get_current_members(self) -> Clan:
        LOGGER.info("Building list of current members...")
        path = f"/clans/{url_encode(self.clan_tag)}"
        raw_members = self.__get_json(path)["memberList"]
        clan = Clan()
        for raw in raw_members:
            last_seen: datetime = parse_timestamp(raw["lastSeen"])
            clan.add(
                ClanMember(
                    tag=raw["tag"],
                    name=raw["name"],
                    role=raw["role"],
                    trophies=raw["trophies"],
                    level=raw["expLevel"],
                    net_donations=raw["donations"] - raw["donationsReceived"],
                    last_seen=last_seen,
                )
            )
        LOGGER.info(f"{len(clan)} current members have been found.")
        return clan

    def get_war_statistics(self, clan: Clan):
        LOGGER.info("Fetching river race statistics...")
        path = f"/clans/{url_encode(self.clan_tag)}/riverracelog"
        river_races = self.__get_json(path)["items"]

        war_statistics = {}
        for player_tag in clan.get_tags():
            war_statistics[player_tag] = {}

        def is_short_war(start: str, end: str) -> bool:
            """ "
            Determine if the war ended early and players didn't have the usual 4 days to accumulate fame.

            Despite what the name suggests, 'start' represents the end time of the war week.
            """
            start_ts: datetime = parse_timestamp(created_at)
            end_ts: datetime = parse_timestamp(finished_at)
            return (start_ts.date() - end_ts.date()).days == 1

        def handle_participants(race_id, participants, short_war: bool):
            for participant in participants:
                tag = participant["tag"]
                if tag in war_statistics:
                    fame = participant["fame"]
                    war_statistics[tag][race_id] = self.__adjust_fame_for_short_war(fame, short_war)

        for river_race in river_races:
            river_race_id = f'{river_race["seasonId"]}.{river_race["sectionIndex"]}'
            created_at: str = river_race["createdDate"]
            for standing in river_race["standings"]:
                clan = standing["clan"]
                if clan["tag"] == self.clan_tag:
                    participants = clan["participants"]
                    finished_at: str = clan["finishTime"]

                    short_war: bool = is_short_war(created_at, finished_at)
                    if short_war:
                        LOGGER.info(
                            f"River race {river_race_id} has finished early. Scaling fame to full week."
                        )
                    LOGGER.debug(
                        f"Date info for {river_race_id}: created_at={created_at}, finished_at={finished_at}"
                    )

                    handle_participants(river_race_id, participants, short_war)

        LOGGER.info("Collection of river race statistics has finished.")
        df = pd.DataFrame.from_dict(war_statistics, orient="index")
        return df.sort_index(axis=1, ascending=False, key=lambda x: x.astype(float))

    def get_current_river_race(self, last_war_id: str) -> pd.Series:
        LOGGER.info("Fetching current river race...")
        path = f"/clans/{url_encode(self.clan_tag)}/currentriverrace"
        current_race = self.__get_json(path)
        section_index = current_race["sectionIndex"]
        clan = current_race["clan"]

        last_war_season_id = int(last_war_id.split(".")[0])
        season_id = last_war_season_id if section_index > 0 else last_war_season_id + 1
        war_id: str = f"{season_id}.{section_index}"

        short_war: bool = "finishTime" in clan
        if short_war:
            finished_at: str = clan["finishTime"]
            LOGGER.info(
                f"Current river race {war_id} has finished early. Scaling fame to full week."
            )
            LOGGER.debug(f"Date info for {war_id}: finished_at={finished_at}")

        current_war_statistics = {}
        for participant in clan["participants"]:
            player_tag = participant["tag"]
            fame: int = int(participant["fame"])
            current_war_statistics[player_tag] = self.__adjust_fame_for_short_war(fame, short_war)
        LOGGER.info("Handling of current river race has finished.")

        return pd.Series(current_war_statistics, name=war_id)

    def get_path_statistics(self, clan: Clan) -> None:
        LOGGER.info(f"Fetching path of legends statistics for all {len(clan)} members...")

        def get_stats_for_player(player: ClanMember):
            raw_player = self.__get_json(f"/players/{url_encode(player.tag)}")

            current_season = raw_player["currentPathOfLegendSeasonResult"]
            previous_season = raw_player["lastPathOfLegendSeasonResult"]

            player.current_season_league_number = current_season["leagueNumber"]
            player.current_season_trophies = current_season["trophies"]
            player.previous_season_league_number = previous_season["leagueNumber"]
            player.previous_season_trophies = previous_season["trophies"]

        with ThreadPoolExecutor() as executor:
            executor.map(lambda player: get_stats_for_player(player), clan.get_members())

        LOGGER.info("Collection of path of legends statistics has finished.")

    def __get_json(self, path: str):
        headers = {"Accept": "application/json", "authorization": f"Bearer {self.api_token}"}
        response = requests.get(API_ENDPOINT + path, headers=headers)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def __adjust_fame_for_short_war(fame: int | str, short_war: bool) -> int:
        """ "
        Short wars end after 3 instead of the usual 4 war days. Adjust the fame to make up the difference.
        """
        if not short_war:
            return int(fame)
        return int(int(fame) * 4 / 3)
