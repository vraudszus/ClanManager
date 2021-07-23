import requests
import json
import pandas as pd

# Rating coefficients - must sum up to 1.0 and values must be >= 0
currentLadderCoefficient = 0.25
previousLadderCoefficient = 0.1
warHistoryCoefficient = 0.45
currentWarCoefficient = 0.2

# New player coefficient is used when a player does not appear in war log
# Must be in interval [0, 1]
newPlayerCoefficient = 0.5

list_of_coefficients = [
    currentLadderCoefficient, 
    previousLadderCoefficient, 
    warHistoryCoefficient, 
    currentWarCoefficient
]
if sum(list_of_coefficients) != 1.0 or min(list_of_coefficients) < 0:
    print("Error: Rating coefficients do not sum up to 1.0 or are negative.")
    exit()
if not 0 <= newPlayerCoefficient <= 1:
    print("NewPlayerCoefficient must be between 0 and 1")
    exit()

clanTag = "#GP9GRQ"
apiToken = open("API-token.txt", "r").read()
# The need for whitelisted IPs causes problems with DHCP.
# To avoid this the proxy of royaleAPI with the whitelisted IP 128.128.128.128 is used
# baseURL = "https://api.clashroyale.com/v1" # URL of official API
baseURL = "https://proxy.royaleapi.dev/v1" # URL of proxy from RoyaleAPI

headers = {}
headers["Accept"] = "application/json"
headers["authorization"] = f"Bearer {apiToken}"

def handle_html_status_code(status_code, response_text):
    if status_code != 200:
        print("Error: Request failed with status code", status_code)
        print(response_text)
        exit()

def get_current_members(clan_tag):
    print("Building list of current members...")
    api_call = f"/clans/%23{clan_tag[1:]}"
    response = requests.get(baseURL + api_call, headers = headers)
    handle_html_status_code(response.status_code, response.text)
    member_list = json.loads(response.text)["memberList"]
    members = {}
    for member in member_list:
        info = {
            "name": member["name"],
        }
        members[member["tag"]] = info
    print(f"{len(members)} current members have been found.")
    return members

def get_ladder_statistics(members):
    print(f"Fetch ladder statistics for all {len(members)} members...")
    ladder_statistics = {}
    for i, player_tag in enumerate(members.keys()):
        print(f"Handling player {i} out of {len(members)}.", end = "\r")
        api_call = f"/players/%23{player_tag[1:]}"
        response = requests.get(baseURL + api_call, headers = headers)
        handle_html_status_code(response.status_code, response.text)
        league_statistics = json.loads(response.text)["leagueStatistics"]
        current_season = league_statistics["currentSeason"]
        previous_season = league_statistics["previousSeason"]
        best_season = league_statistics["bestSeason"]
        ladder_statistics[player_tag] = {
            "current_season_best_trophies": current_season["bestTrophies"],
            "current_season_trophies": current_season["trophies"],
            "previous_season_best_trophies": previous_season["bestTrophies"],
            "previous_season_trophies": previous_season["trophies"],
            "best_season_trophies": best_season["trophies"],
        }
    print("Collection of ladder statistics has finished.")
    return pd.DataFrame.from_dict(ladder_statistics, orient = "index")

def get_war_statistics(clan_tag, members):
    print("Fetch river race statistics...")
    api_call = f"/clans/%23{clan_tag[1:]}/riverracelog"
    response = requests.get(baseURL + api_call, headers = headers)
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
            if clan["tag"] == clanTag:
                for participant in clan["participants"]:
                    player_tag = participant["tag"]
                    if player_tag in war_statistics:
                        war_statistics[player_tag][river_race_id] = int(participant["fame"])
    print("Collection of river race statistics has finished.")
    return pd.DataFrame.from_dict(war_statistics, orient = "index")

def get_current_river_race(clan_tag):
    print("Fetch current river race...")
    api_call = f"/clans/%23{clan_tag[1:]}/currentriverrace"
    response = requests.get(baseURL + api_call, headers = headers)
    handle_html_status_code(response.status_code, response.text)
    clan = json.loads(response.text)["clan"]

    current_war_statistics = {}
    for participant in clan["participants"]:
        player_tag = participant["tag"]
        current_war_statistics[player_tag] = int(participant["fame"])
    print("Handling of current river race has finished.")
    return pd.Series(current_war_statistics)

def evaluate_performance(members, ladder_stats, war_log, current_war):
    current_season_max_trophies = ladder_stats["current_season_best_trophies"].max()
    current_season_min_trophies = ladder_stats["current_season_best_trophies"].min()
    current_season_trophy_range = current_season_max_trophies - current_season_min_trophies
    previous_season_max_trophies = ladder_stats["previous_season_best_trophies"].max()
    previous_season_min_trophies = ladder_stats["previous_season_best_trophies"].min()
    previous_season_trophy_range = previous_season_max_trophies - previous_season_min_trophies
    war_log["mean"] = war_log.mean(axis = 1)
    war_log_max_fame = war_log["mean"].max()
    war_log_min_fame = war_log["mean"].min()
    war_history_fame_range = war_log_max_fame - war_log_min_fame
    current_max_fame = current_war.max()
    current_min_fame = current_war.min()
    current_fame_range = current_max_fame - current_min_fame
    new_player_war_log_mean = war_log_min_fame + war_history_fame_range * newPlayerCoefficient

    for player_tag in members.keys():
        current_best_trophies = ladder_stats.at[player_tag, "current_season_best_trophies"]
        current_ladder_rating = (current_best_trophies - current_season_min_trophies) / current_season_trophy_range
        previous_best_trophies = ladder_stats.at[player_tag, "previous_season_best_trophies"]
        previous_ladder_rating = (previous_best_trophies - previous_season_min_trophies) / previous_season_trophy_range
        war_log_mean = war_log.at[player_tag, "mean"] if player_tag in war_log.index else new_player_war_log_mean
        war_log_rating = (war_log_mean - war_log_min_fame) / war_history_fame_range
        current_fame = current_war[player_tag]
        current_war_rating = (current_fame - current_min_fame) / current_fame_range

        members[player_tag]["rating"] = (currentLadderCoefficient * current_ladder_rating
                                        + previousLadderCoefficient * previous_ladder_rating
                                        + currentWarCoefficient * current_war_rating
                                        + warHistoryCoefficient * war_log_rating)
        members[player_tag]["current_season"] = current_ladder_rating
        members[player_tag]["previous_season"] = previous_ladder_rating
        members[player_tag]["current_war"] = current_war_rating
        members[player_tag]["war_history"] = war_log_rating
    performance = pd.DataFrame.from_dict(members, orient = "index")
    return performance.sort_values("rating")

print(f"Evaluating performance of players from {clanTag}...")
members = get_current_members(clanTag)
warStatistics = get_war_statistics(clanTag, members)
currentWar = get_current_river_race(clanTag)
ladderStatistics = get_ladder_statistics(members)

performance = evaluate_performance(members, ladderStatistics, warStatistics, currentWar)
print(performance)