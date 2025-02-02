import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple
import requests
import pandas as pd

from player_ranking.models.clan import Clan, ClanMember

# URL of the proxy provided by RoyaleAPI.com
# Alternatively you can use the official URL "https://api.clashroyale.com/v1"
# Dynamic IPs don't work with the official URL as the IP must be whitelisted
API_ENDPOINT: str = "https://proxy.royaleapi.dev/v1"
LOGGER = logging.getLogger(__name__)


def get_current_members(clan_tag, api_token) -> Clan:
    LOGGER.info("Building list of current members...")
    path = f"/clans/%23{clan_tag[1:]}"
    raw_members = _get_json_from_api(path, api_token)["memberList"]
    clan = Clan()
    for raw in raw_members:
        clan.add(ClanMember(tag=raw["tag"], name=raw["name"], role=raw["role"], trophies=raw["trophies"]))
    LOGGER.info(f"{len(clan)} current members have been found.")
    return clan


def get_war_statistics(clan_tag, clan: Clan, api_token):
    LOGGER.info("Fetching river race statistics...")
    path = f"/clans/%23{clan_tag[1:]}/riverracelog"
    river_races = _get_json_from_api(path, api_token)["items"]

    war_statistics = {}
    for player_tag in clan.get_tags():
        war_statistics[player_tag] = {}

    def handle_participants(race_id, participants):
        for participant in participants:
            tag = participant["tag"]
            if tag in war_statistics:
                war_statistics[tag][race_id] = int(participant["fame"])

    for river_race in river_races:
        river_race_id = f'{river_race["seasonId"]}.{river_race["sectionIndex"]}'
        for standing in river_race["standings"]:
            clan = standing["clan"]
            if clan["tag"] == clan_tag:
                handle_participants(river_race_id, clan["participants"])

    LOGGER.info("Collection of river race statistics has finished.")
    df = pd.DataFrame.from_dict(war_statistics, orient="index")
    return df.sort_index(axis=1, ascending=False, key=lambda x: x.astype(float))


def get_current_river_race(clan_tag, api_token):
    LOGGER.info("Fetching current river race...")
    path = f"/clans/%23{clan_tag[1:]}/currentriverrace"
    clan = _get_json_from_api(path, api_token)["clan"]

    current_war_statistics = {}
    for participant in clan["participants"]:
        player_tag = participant["tag"]
        current_war_statistics[player_tag] = int(participant["fame"])
    LOGGER.info("Handling of current river race has finished.")
    return pd.Series(current_war_statistics)


def get_path_statistics(clan: Clan, api_token):
    LOGGER.info(f"Fetching path of legends statistics for all {len(clan)} members...")

    def get_stats_for_player(player_tag: str) -> Tuple[str, dict[str, int]]:
        player = _get_json_from_api(f"/players/%23{player_tag[1:]}", api_token)

        current_season = player["currentPathOfLegendSeasonResult"]
        previous_season = player["lastPathOfLegendSeasonResult"]

        stats = {
            "current_season_league_number": current_season["leagueNumber"],
            "current_season_trophies": current_season["trophies"],
            "previous_season_league_number": previous_season["leagueNumber"],
            "previous_season_trophies": previous_season["trophies"],
        }
        return player_tag, stats

    with ThreadPoolExecutor() as executor:
        path_statistics = dict(executor.map(lambda tag: get_stats_for_player(tag), clan.get_tags()))

    LOGGER.info("Collection of path of legends statistics has finished.")
    return pd.DataFrame.from_dict(path_statistics, orient="index")


def _get_json_from_api(path: str, api_token: str):
    headers = {"Accept": "application/json", "authorization": f"Bearer {api_token}"}
    response = requests.get(API_ENDPOINT + path, headers=headers)
    response.raise_for_status()
    return response.json()
