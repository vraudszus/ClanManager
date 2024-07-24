import requests
import json
import pandas as pd


def prepare_headers(api_token_path):
    api_token = open(api_token_path, "r").read()
    headers = {
        "Accept": "application/json",
        "authorization": f"Bearer {api_token}"
    }
    return headers


def handle_html_status_code(status_code, response_text):
    if status_code != 200:
        print("Error: Request failed with status code", status_code)
        print(response_text)
        exit()


def get_current_members(clan_tag, api_token_path, base_url):
    print("Building list of current members...")
    api_call = f"/clans/%23{clan_tag[1:]}"
    response = requests.get(base_url + api_call, headers=prepare_headers(api_token_path))
    handle_html_status_code(response.status_code, response.text)
    member_list = json.loads(response.text)["memberList"]
    members = {}
    for member in member_list:
        info = {
            "name": member["name"],
            "role": member["role"],
            "trophies": member["trophies"],
            "clanRank": member["clanRank"],
        }
        members[member["tag"]] = info
    print(f"{len(members)} current members have been found.")
    return members


def get_war_statistics(clan_tag, members, api_token_path, base_url):
    print("Fetching river race statistics...")
    api_call = f"/clans/%23{clan_tag[1:]}/riverracelog"
    response = requests.get(base_url + api_call, headers=prepare_headers(api_token_path))
    handle_html_status_code(response.status_code, response.text)
    river_races = json.loads(response.text)["items"]

    war_statistics = {}
    for player_tag in members.keys():
        war_statistics[player_tag] = {}

    def handle_participants(race_id, participants):
        for participant in participants:
            player_tag = participant["tag"]
            if player_tag in war_statistics:
                war_statistics[player_tag][race_id] = int(participant["fame"])

    for river_race in river_races:
        river_race_id = f'{river_race["seasonId"]}.{river_race["sectionIndex"]}'
        for standing in river_race["standings"]:
            clan = standing["clan"]
            if clan["tag"] == clan_tag:
                handle_participants(river_race_id, clan["participants"])

    print("Collection of river race statistics has finished.")
    df = pd.DataFrame.from_dict(war_statistics, orient="index")
    return df.sort_index(axis=1, ascending=False, key=lambda x: x.astype(float))


def get_current_river_race(clan_tag, api_token_path, base_url):
    print("Fetching current river race...")
    api_call = f"/clans/%23{clan_tag[1:]}/currentriverrace"
    response = requests.get(base_url + api_call, headers=prepare_headers(api_token_path))
    handle_html_status_code(response.status_code, response.text)
    clan = json.loads(response.text)["clan"]

    current_war_statistics = {}
    for participant in clan["participants"]:
        player_tag = participant["tag"]
        current_war_statistics[player_tag] = int(participant["fame"])
    print("Handling of current river race has finished.")
    return pd.Series(current_war_statistics)

def get_path_statistics(members, api_token_path, base_url):
    print(f"Fetching path of legends statistics for all {len(members)} members...")
    path_statistics = {}
    for i, player_tag in enumerate(members.keys()):
        print(f"Handling player {i+1} out of {len(members)}.", end="\r")
        api_call = f"/players/%23{player_tag[1:]}"
        response = requests.get(base_url + api_call, headers=prepare_headers(api_token_path))
        handle_html_status_code(response.status_code, response.text)
        player = json.loads(response.text)

        current_season = player["currentPathOfLegendSeasonResult"]
        previous_season = player["lastPathOfLegendSeasonResult"]

        path_statistics[player_tag] = {
            "current_season_league_number": current_season["leagueNumber"],
            "current_season_trophies": current_season["trophies"],
            "previous_season_league_number": previous_season["leagueNumber"],
            "previous_season_trophies": previous_season["trophies"],
        }
    print("Collection of path of legends statistics has finished.")
    return pd.DataFrame.from_dict(path_statistics, orient="index")
