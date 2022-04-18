import requests
import json
import pandas as pd
import datetime
import argparse
import numpy as np
import math
import gsheetsManager

CLI = argparse.ArgumentParser()
CLI.add_argument(
  "--ignore_wars",
  nargs="*",
  type = int,
)

# Rating coefficients - must sum up to 1.0 and values must be >= 0
currentLadderCoefficient = 0.25
previousLadderCoefficient = 0.1
warHistoryCoefficient = 0.4
currentWarCoefficient = 0.25

# New player coefficient is used when a player does not appear in war log
# Must be in interval [0, 1]
newPlayerCoefficient = 0.5

# Promotion/demotion requirements
minFameForCountingWar = 2000
minCountingWars = 8

warProgress = 1.0 # ranges from 0 to 1

VALID_EXCUSES = ["nicht im Clan", "abgemeldet", "Neuling"]

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

def get_adjusted_war_weights(current_war_weight, war_history_weight):
    now = datetime.datetime.utcnow()
    seconds_since_midnight = (now - now.replace(hour=10, minute=0, second=0, microsecond=0)).total_seconds()
    offset = (now.weekday() - 3) % 7
    # Find datetime for last Thursday 10:00 am UTC (roughly the begin of the war days)
    begin_of_war_days = now - datetime.timedelta(days = offset, seconds = seconds_since_midnight)
    time_since_start = now - begin_of_war_days
    if time_since_start > datetime.timedelta(days = 4):
        # Training days are currently happening, do not count current war
        return (0, current_war_weight + war_history_weight)
    else:
        # War days are currently happening
        # Linearly increase weight for current war
        global warProgress
        warProgress = time_since_start / datetime.timedelta(days = 4)
        print("progress:", warProgress)
        return (current_war_weight * warProgress, war_history_weight + current_war_weight * (1 - warProgress))

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
            "role": member["role"],
        }
        members[member["tag"]] = info
    print(f"{len(members)} current members have been found.")
    return members

def get_ladder_statistics(members):
    print(f"Fetching ladder statistics for all {len(members)} members...")
    ladder_statistics = {}
    for i, player_tag in enumerate(members.keys()):
        print(f"Handling player {i} out of {len(members)}.", end = "\r")
        api_call = f"/players/%23{player_tag[1:]}"
        response = requests.get(baseURL + api_call, headers = headers)
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

def get_war_statistics(clan_tag, members):
    print("Fetching river race statistics...")
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
    print("Fetching current river race...")
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

def ignore_selected_wars(currentWar, warLog, ignore_wars):
    if ignore_wars:
        for value in ignore_wars:
            if value == 0:
                currentWar.values[:] = 0
            else:
                warLog.iloc[:, -value-1] = np.nan
    return currentWar, warLog

def handle_excuses(service, current_war, war_log, members):
    excuses = gsheetsManager.get_excuses("Abmeldungen", service)
    for tag in current_war.items():
        if tag in members and excuses.at[members[tag]["name"], "current"] in VALID_EXCUSES:
            current_war.at[tag] = 1600 * warProgress
            print("Excuse accepted for current CW:", excuses.at[members[tag]["name"], "current"], members[tag]["name"])
    for war_id in war_log[0:9]:
        war = war_log[war_id]
        for tag, fame in war.items():
            if tag in members:
                excuse = excuses.at[members[tag]["name"], war.name]
                if not math.isnan(fame) and excuse in VALID_EXCUSES:
                    war_log.at[tag, war.name] = 1600 
                    print("Excuse accepted for", war.name, excuse, members[tag]["name"])
    return current_war, war_log   

def evaluate_performance(members, ladder_stats, war_log, current_war, ignore_wars, service):
    current_war, war_log = ignore_selected_wars(current_war, war_log, ignore_wars)
    current_war, war_log = handle_excuses(service, current_war, war_log, members)
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

    current_war_coefficient, war_history_coefficient = get_adjusted_war_weights(currentWarCoefficient, warHistoryCoefficient)

    for player_tag in members.keys():
        current_best_trophies = ladder_stats.at[player_tag, "current_season_best_trophies"]
        current_ladder_rating = (current_best_trophies - current_season_min_trophies) / current_season_trophy_range
        previous_best_trophies = ladder_stats.at[player_tag, "previous_season_best_trophies"]
        previous_ladder_rating = (previous_best_trophies - previous_season_min_trophies) / previous_season_trophy_range
        war_log_mean = war_log.at[player_tag, "mean"] if player_tag in war_log.index else new_player_war_log_mean
        war_log_rating = (war_log_mean - war_log_min_fame) / war_history_fame_range
        if player_tag in war_log.index:
            war_log_mean_without_first_war = war_log.loc[player_tag].drop("mean").dropna()[:-1].mean()
        else:
            war_log_mean_without_first_war = None
        # player_tag is not present in current_war until a user has log in after season reset
        current_fame = current_war[player_tag] if player_tag in current_war else 0
        if current_fame_range > 0:
            current_war_rating = (current_fame - current_min_fame) / current_fame_range
        else:
            # Default value that is used during trainings days.
            # Does not affect the rating on those days
            current_war_rating = 1

        members[player_tag]["rating"] = (currentLadderCoefficient * current_ladder_rating
                                        + previousLadderCoefficient * previous_ladder_rating
                                        + current_war_coefficient * current_war_rating
                                        + war_history_coefficient * war_log_rating)
        members[player_tag]["current_season"] = current_ladder_rating
        members[player_tag]["previous_season"] = previous_ladder_rating
        members[player_tag]["current_war"] = current_war_rating
        members[player_tag]["war_history"] = war_log_rating
        members[player_tag]["avg_fame"] = int(war_log.at[player_tag, "mean"]) if player_tag in war_log.index else None
        members[player_tag]["avg_fame[:-1]"] = war_log_mean_without_first_war

    performance = pd.DataFrame.from_dict(members, orient = "index")
    performance["avg_fame"] = np.floor(pd.to_numeric(performance["avg_fame"], errors='coerce')).astype('Int64')
    performance["avg_fame[:-1]"] = np.floor(pd.to_numeric(performance["avg_fame[:-1]"], errors='coerce')).astype('Int64')
    print("Performance rating calculated according to the following formula:")
    print("rating =",
        "{:.2f}".format(currentLadderCoefficient), "* current_season",
        "{:.2f}".format(previousLadderCoefficient), "* previous_season",
        "{:.2f}".format(current_war_coefficient), "* current_war",
        "{:.2f}".format(war_history_coefficient), "* war_history"
    )
    return performance.sort_values("rating", ascending = False)

def print_pending_rank_changes(members, war_log, min_fame, min_wars):
    warLog = war_log.drop("mean", axis=1)
    # promotions
    only_members = dict((k, v["name"]) for (k,v) in members.items() if v["role"] == "member")
    promotion_deserving_logs = warLog[warLog >= min_fame].count(axis="columns")
    promotion_deserving_logs = promotion_deserving_logs[promotion_deserving_logs >= min_wars]
    promotion_deserving_logs = promotion_deserving_logs[promotion_deserving_logs.index.isin(only_members.keys())]
    promotion_deserving_logs = list(promotion_deserving_logs.index.map(lambda k: only_members[k]))
    if promotion_deserving_logs:
        print("Pending promotions for:", ', '.join(promotion_deserving_logs))
    # demotions
    only_elders = dict((k, v["name"]) for (k,v) in members.items() if v["role"] == "elder")
    demotion_deserving_logs = warLog[warLog >= min_fame].count(axis="columns")
    demotion_deserving_logs = demotion_deserving_logs[demotion_deserving_logs < min_wars]
    demotion_deserving_logs = demotion_deserving_logs[demotion_deserving_logs.index.isin(only_elders.keys())]
    demotion_deserving_logs = list(demotion_deserving_logs.index.map(lambda k: only_elders[k]))
    if demotion_deserving_logs:
        print("Pending demotions for:", ', '.join(demotion_deserving_logs))

args = CLI.parse_args()
print(f"Evaluating performance of players from {clanTag}...")
members = get_current_members(clanTag)
warStatistics = get_war_statistics(clanTag, members)
currentWar = get_current_river_race(clanTag)
ladderStatistics = get_ladder_statistics(members)

service = gsheetsManager.connect_to_service()
performance = evaluate_performance(members, ladderStatistics, warStatistics, currentWar, args.ignore_wars, service)
performance = performance.reset_index(drop = True)
performance.index += 1
print(performance)
print_pending_rank_changes(members, warStatistics, minFameForCountingWar, minCountingWars)

performance.to_csv("player-ranking.csv", sep = ";", float_format= "%.3f")
gsheetsManager.write_player_ranking(performance, "PlayerRanking", service)
gsheetsManager.update_excuse_sheet(members, currentWar, warStatistics, "Abmeldungen", service)
input()