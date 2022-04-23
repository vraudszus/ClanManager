import pandas as pd
import datetime
import argparse
import numpy as np
import math
import yaml

import gsheeetsApiWrapper
import crApiWrapper

CLI = argparse.ArgumentParser()
CLI.add_argument(
  "--ignore_wars",
  nargs="*",
  type = int,
)

def check_coefficients(rating_coefficients):
    rating_coefficients_list = list(rating_coefficients.values())
    if sum(rating_coefficients_list) != 1.0 or min(rating_coefficients_list) < 0:
        print("Error: Rating coefficients do not sum up to 1.0 or are negative.")
        exit()

def adjust_war_weights(rating_coefficients):
    now = datetime.datetime.utcnow()
    seconds_since_midnight = (now - now.replace(hour=10, minute=0, second=0, microsecond=0)).total_seconds()
    offset = (now.weekday() - 3) % 7
    # Find datetime for last Thursday 10:00 am UTC (roughly the begin of the war days)
    begin_of_war_days = now - datetime.timedelta(days = offset, seconds = seconds_since_midnight)
    time_since_start = now - begin_of_war_days
    if time_since_start > datetime.timedelta(days = 4):
        # Training days are currently happening, do not count current war
        war_progress = 0
        rating_coefficients["warHistoryCoefficient"] += rating_coefficients["currentWarCoefficient"]
        rating_coefficients["currentWarCoefficient"] = 0
    else:
        # War days are currently happening
        # Linearly increase weight for current war
        war_progress = time_since_start / datetime.timedelta(days = 4) # ranges from 0 to 1
        rating_coefficients["warHistoryCoefficient"] += rating_coefficients["currentWarCoefficient"] * (1 - war_progress)
        rating_coefficients["currentWarCoefficient"] *= war_progress
    print("War progress:", war_progress)
    return (war_progress, rating_coefficients)

def ignore_selected_wars(current_war, war_log, ignore_wars):
    if ignore_wars:
        for value in ignore_wars:
            if value == 0:
                current_war.values[:] = 0
            else:
                war_log.iloc[:, -value-1] = np.nan
    return current_war, war_log

def accept_excuses(service, current_war, war_log, members, valid_excuses, war_progress, gsheet_spreadsheet_id):
    excuses = gsheeetsApiWrapper.get_excuses("Abmeldungen", service, gsheet_spreadsheet_id)
       
    def handle_war(tag, name, war, fame):
        excuse = excuses.at[name, war]
        if not math.isnan(fame) and excuse in valid_excuses.values():
            if excuse == valid_excuses["notInClanExcuse"] or excuse == valid_excuses["newPlayerExcuse"]:
                war_log.at[tag, war] = np.nan
            else:
                war_log.at[tag, war] = 1600 
            print("Excuse accepted for", war, excuse, name)
                
    def handle_current_war(tag, name):
        excuse = excuses.at[name, "current"]
        if excuse in valid_excuses.values():
            if excuse == valid_excuses["newPlayerExcuse"]:
                current_war.at[tag] = np.nan
            else:
                current_war.at[tag] = 1600 * war_progress
            print("Excuse accepted for current CW:", excuse, name)
    
    for tag in members:
        name = members[tag]["name"]
        if name in excuses.index:
            handle_current_war(tag, name)
            for war, fame in war_log.loc[tag].items():
                handle_war(tag, name, war, fame)
    return current_war, war_log   

def evaluate_performance(members, ladder, war_log, current_war, rating_coefficients):
    current_season_max_trophies = ladder["current_season_best_trophies"].max()
    current_season_min_trophies = ladder["current_season_best_trophies"].min()
    current_season_trophy_range = current_season_max_trophies - current_season_min_trophies
    previous_season_max_trophies = ladder["previous_season_best_trophies"].max()
    previous_season_min_trophies = ladder["previous_season_best_trophies"].min()
    previous_season_trophy_range = previous_season_max_trophies - previous_season_min_trophies
    war_log["mean"] = war_log.mean(axis = 1)
    war_log_max_fame = war_log["mean"].max()
    war_log_min_fame = war_log["mean"].min()
    war_history_fame_range = war_log_max_fame - war_log_min_fame
    current_max_fame = current_war.max()
    current_min_fame = current_war.min()
    current_fame_range = current_max_fame - current_min_fame

    for player_tag in members.keys():
        current_best_trophies = ladder.at[player_tag, "current_season_best_trophies"]
        current_ladder_rating = (current_best_trophies - current_season_min_trophies) / current_season_trophy_range
        previous_best_trophies = ladder.at[player_tag, "previous_season_best_trophies"]
        previous_ladder_rating = (previous_best_trophies - previous_season_min_trophies) / previous_season_trophy_range
        war_log_mean = war_log.at[player_tag, "mean"] if player_tag in war_log.index else None
        war_log_rating = (war_log_mean - war_log_min_fame) / war_history_fame_range
        # player_tag is not present in current_war until a user has logged in after season reset
        current_fame = current_war[player_tag] if player_tag in current_war else 0
        if current_fame_range > 0:
            current_war_rating = (current_fame - current_min_fame) / current_fame_range
        else:
            # Default value that is used during trainings days.
            # Does not affect the rating on those days
            current_war_rating = 1

        members[player_tag]["rating"] = (rating_coefficients["currentLadderCoefficient"] * current_ladder_rating
                                        + rating_coefficients["previousLadderCoefficient"] * previous_ladder_rating
                                        + rating_coefficients["currentWarCoefficient"] * current_war_rating
                                        + rating_coefficients["warHistoryCoefficient"] * war_log_rating) * 1000
        members[player_tag]["current_season"] = current_ladder_rating * 1000
        members[player_tag]["previous_season"] = previous_ladder_rating * 1000
        members[player_tag]["current_war"] = current_war_rating * 1000
        members[player_tag]["war_history"] = war_log_rating * 1000
        members[player_tag]["avg_fame"] = war_log.at[player_tag, "mean"] if player_tag in war_log.index else np.nan
        
    performance = pd.DataFrame.from_dict(members, orient = "index")
    
    print("Performance rating calculated according to the following formula:")
    print("rating =",
        "{:.2f}".format(rating_coefficients["currentLadderCoefficient"]), "* current_season +",
        "{:.2f}".format(rating_coefficients["previousLadderCoefficient"]), "* previous_season +",
        "{:.2f}".format(rating_coefficients["currentWarCoefficient"]), "* current_war +",
        "{:.2f}".format(rating_coefficients["warHistoryCoefficient"]), "* war_history"
    )
    return performance.sort_values("rating", ascending = False)

def print_pending_rank_changes(members, war_log, requirements):
    war_log = war_log.copy()
    war_log = war_log.drop("mean", axis=1)
    min_fame = requirements["minFameForCountingWar"]
    min_wars = requirements["minCountingWars"]
    # promotions
    only_members = dict((k, v["name"]) for (k,v) in members.items() if v["role"] == "member")
    promotion_deserving_logs = war_log[war_log >= min_fame].count(axis="columns")
    promotion_deserving_logs = promotion_deserving_logs[promotion_deserving_logs >= min_wars]
    promotion_deserving_logs = promotion_deserving_logs[promotion_deserving_logs.index.isin(only_members.keys())]
    promotion_deserving_logs = list(promotion_deserving_logs.index.map(lambda k: only_members[k]))
    if promotion_deserving_logs:
        print("Pending promotions for:", ', '.join(promotion_deserving_logs))
    # demotions
    only_elders = dict((k, v["name"]) for (k,v) in members.items() if v["role"] == "elder")
    demotion_deserving_logs = war_log[war_log >= min_fame].count(axis="columns")
    demotion_deserving_logs = demotion_deserving_logs[demotion_deserving_logs < min_wars]
    demotion_deserving_logs = demotion_deserving_logs[demotion_deserving_logs.index.isin(only_elders.keys())]
    demotion_deserving_logs = list(demotion_deserving_logs.index.map(lambda k: only_elders[k]))
    if demotion_deserving_logs:
        print("Pending demotions for:", ', '.join(demotion_deserving_logs))
        
def main():
    args = CLI.parse_args()
    
    props = yaml.safe_load(open("properties.yaml", "r"))  
    clan_tag = props["clanTag"]
    cr_api_url = props["crApiUrl"]
    api_tokens = props["apiTokens"]
    cr_token = api_tokens["crApiTokenPath"]
    gsheet_credentials = api_tokens["gsheetsCredentialsPath"]
    gsheet_token = api_tokens["gsheetsTokenPath"]
    rating_coefficients = props["ratingCoefficients"]
    valid_excuses = props["valid_excuses"]
    not_in_clan_excuse = valid_excuses["notInClanExcuse"]
    pro_demotion_requirements = props["promotion_demotion_requirements"]
    rating_file = props["ratingFile"]
    rating_gsheet = props["gsheetNames"]["rating"]
    excuses_gsheet = props["gsheetNames"]["excuses"]
    gsheet_spreadsheet_id = props["gsheet_spreadsheet_id"]
              
    check_coefficients(rating_coefficients)
    print(f"Evaluating performance of players from {clan_tag}...")
    members = crApiWrapper.get_current_members(clan_tag, cr_token, cr_api_url)
    war_log = crApiWrapper.get_war_statistics(clan_tag, members, cr_token, cr_api_url)
    current_war = crApiWrapper.get_current_river_race(clan_tag, cr_token, cr_api_url)
    ladder = crApiWrapper.get_ladder_statistics(members, cr_token, cr_api_url)

    service = gsheeetsApiWrapper.connect_to_service(gsheet_credentials, gsheet_token)
    
    war_progress, rating_coefficients = adjust_war_weights(rating_coefficients)
    current_war, war_log = ignore_selected_wars(current_war, war_log, args.ignore_wars)
    current_war, war_log = accept_excuses(service, current_war, war_log, members, valid_excuses, war_progress, gsheet_spreadsheet_id)
    performance = evaluate_performance(members, ladder, war_log, current_war, rating_coefficients)
    performance = performance.reset_index(drop = True)
    performance.index += 1
    performance.loc["mean"] = performance.mean()
    performance.loc["median"] = performance.median()
    print(performance)
    print_pending_rank_changes(members, war_log, pro_demotion_requirements)

    performance.to_csv(rating_file, sep = ";", float_format= "%.0f")
    gsheeetsApiWrapper.write_player_ranking(performance, rating_gsheet, service, gsheet_spreadsheet_id)
    gsheeetsApiWrapper.update_excuse_sheet(members, current_war, war_log, not_in_clan_excuse, excuses_gsheet, service, gsheet_spreadsheet_id)

if __name__ == "__main__":
    main()