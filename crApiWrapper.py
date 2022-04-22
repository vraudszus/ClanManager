import requests
import json
import pandas as pd

# The need for whitelisted IPs causes problems with DHCP.
# To avoid this the proxy of royaleAPI with the whitelisted IP 128.128.128.128 is used
# "https://api.clashroyale.com/v1" # URL of official API
BASE_URL = "https://proxy.royaleapi.dev/v1" # URL of proxy from RoyaleAPI

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

def get_current_members(clan_tag, api_token_path):
    print("Building list of current members...")
    api_call = f"/clans/%23{clan_tag[1:]}"
    response = requests.get(BASE_URL + api_call, headers = prepare_headers(api_token_path))
    handle_html_status_code(response.status_code, response.text)
    member_list = json.loads(response.text)["memberList"]
    members = {}
    for member in member_list:
        info = {
            "name": member["name"],
            "role": member["role"],
        }
        members[member["tag"]] = info
    print(f"{len(members)} current members have been found.")
    return members

def get_ladder_statistics(members, api_token_path):
    print(f"Fetching ladder statistics for all {len(members)} members...")
    ladder_statistics = {}
    for i, player_tag in enumerate(members.keys()):
        print(f"Handling player {i} out of {len(members)}.", end = "\r")
        api_call = f"/players/%23{player_tag[1:]}"
        response = requests.get(BASE_URL + api_call, headers = prepare_headers(api_token_path))
        handle_html_status_code(response.status_code, response.text)
        league_statistics = json.loads(response.text)["leagueStatistics"]
        
        if "previousSeason" in league_statistics:
            current_season = league_statistics["currentSeason"]
            previous_season = league_statistics["previousSeason"]
        else:
            # handle case when a user has not yet logged in after season reset
            current_season = {"trophies": 5001} # check how this works for non-league players
            previous_season = league_statistics["currentSeason"]

        best_season = league_statistics["bestSeason"]
        ladder_statistics[player_tag] = {
            "current_season_best_trophies": current_season["bestTrophies"] if "bestTrophies" in current_season.keys() else current_season["trophies"],
            "current_season_trophies": current_season["trophies"],
            "previous_season_best_trophies": previous_season["bestTrophies"] if "bestTrophies" in previous_season.keys() else None,
            "previous_season_trophies": previous_season["trophies"] if "trophies" in previous_season.keys() else None,
            "best_season_trophies": best_season["trophies"],
        }
    print("Collection of ladder statistics has finished.")
    return pd.DataFrame.from_dict(ladder_statistics, orient = "index")

def get_war_statistics(clan_tag, members, api_token_path):
    print("Fetching river race statistics...")
    api_call = f"/clans/%23{clan_tag[1:]}/riverracelog"
    response = requests.get(BASE_URL + api_call, headers = prepare_headers(api_token_path))
    handle_html_status_code(response.status_code, response.text)
    river_races = json.loads(response.text)["items"]

    war_statistics = {}
    for player_tag in members.keys():
        war_statistics[player_tag] = {}

    for river_race in river_races:
        river_race_id = f'{river_race["seasonId"]}.{river_race["sectionIndex"]}'
        standings = river_race["standings"]
        for standing in standings:
            clan = standing["clan"]
            if clan["tag"] == clan_tag:
                for participant in clan["participants"]:
                    player_tag = participant["tag"]
                    if player_tag in war_statistics:
                        war_statistics[player_tag][river_race_id] = int(participant["fame"])
    print("Collection of river race statistics has finished.")
    return pd.DataFrame.from_dict(war_statistics, orient = "index")

def get_current_river_race(clan_tag, api_token_path):
    print("Fetching current river race...")
    api_call = f"/clans/%23{clan_tag[1:]}/currentriverrace"
    response = requests.get(BASE_URL + api_call, headers = prepare_headers(api_token_path))
    handle_html_status_code(response.status_code, response.text)
    clan = json.loads(response.text)["clan"]

    current_war_statistics = {}
    for participant in clan["participants"]:
        player_tag = participant["tag"]
        current_war_statistics[player_tag] = int(participant["fame"])
    print("Handling of current river race has finished.")
    return pd.Series(current_war_statistics)