import pandas as pd
import datetime
import argparse
import numpy as np
import math

import gsheeetsApiWrapper
import crApiWrapper

CLI = argparse.ArgumentParser()
CLI.add_argument(
  "--ignore_wars",
  nargs="*",
  type = int,
)

CR_API_TOKEN_PATH = "API-token.txt"
GSHEETS_CREDENTIALS_PATH = "credentials.json"
GSHEETS_TOKEN_PATH = "token.json"

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

# excuses (valid values for cells  in "Abmeldungen" gsheet)
NOT_IN_CLAN_EXCUSE = "nicht im Clan"
NEW_PLAYER_EXCUSE = "Neuling"
PERSONAL_EXCUSE = "abgemeldet"
VALID_EXCUSES = [NOT_IN_CLAN_EXCUSE, NEW_PLAYER_EXCUSE, PERSONAL_EXCUSE]

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

def ignore_selected_wars(currentWar, warLog, ignore_wars):
    if ignore_wars:
        for value in ignore_wars:
            if value == 0:
                currentWar.values[:] = 0
            else:
                warLog.iloc[:, -value-1] = np.nan
    return currentWar, warLog

def accept_excuses(service, current_war, war_log, members):
       
    def handle_war(tag, name, war, fame):
        excuse = excuses.at[name, war]
        if not math.isnan(fame) and excuse in VALID_EXCUSES:
            if (excuse == NOT_IN_CLAN_EXCUSE):
                war_log.at[tag, war] = np.nan
            else:
                war_log.at[tag, war] = 1600 
            print("Excuse accepted for", war, excuse, name)
                
    def handle_current_war(tag, name):
        if excuses.at[name, "current"] in VALID_EXCUSES:
            current_war.at[tag] = 1600 * warProgress
            print("Excuse accepted for current CW:", excuses.at[name, "current"], name)
    
    excuses = gsheeetsApiWrapper.get_excuses("Abmeldungen", service)
    for tag in members:
        name = members[tag]["name"]
        if name in excuses.index:
            handle_current_war(tag, name)
            for war, fame in war_log.loc[tag].items():
                handle_war(tag, name, war, fame)
    return current_war, war_log   

def evaluate_performance(members, ladder_stats, war_log, current_war, ignore_wars, service):
    current_war, war_log = ignore_selected_wars(current_war, war_log, ignore_wars)
    current_war, war_log = accept_excuses(service, current_war, war_log, members)
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
        # player_tag is not present in current_war until a user has logged in after season reset
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
        "{:.2f}".format(currentLadderCoefficient), "* current_season +",
        "{:.2f}".format(previousLadderCoefficient), "* previous_season +",
        "{:.2f}".format(current_war_coefficient), "* current_war +",
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
members = crApiWrapper.get_current_members(clanTag, CR_API_TOKEN_PATH)
warStatistics = crApiWrapper.get_war_statistics(clanTag, members, CR_API_TOKEN_PATH)
currentWar = crApiWrapper.get_current_river_race(clanTag, CR_API_TOKEN_PATH)
ladderStatistics = crApiWrapper.get_ladder_statistics(members, CR_API_TOKEN_PATH)

service = gsheeetsApiWrapper.connect_to_service(GSHEETS_CREDENTIALS_PATH, GSHEETS_TOKEN_PATH)
performance = evaluate_performance(members, ladderStatistics, warStatistics, currentWar, args.ignore_wars, service)
performance = performance.reset_index(drop = True)
performance.index += 1
print(performance)
print_pending_rank_changes(members, warStatistics, minFameForCountingWar, minCountingWars)

performance.to_csv("player-ranking.csv", sep = ";", float_format= "%.3f")
gsheeetsApiWrapper.write_player_ranking(performance, "PlayerRanking", service)
gsheeetsApiWrapper.update_excuse_sheet(members, currentWar, warStatistics, NOT_IN_CLAN_EXCUSE, "Abmeldungen", service)

input() # only to prevent console window from closing after execution