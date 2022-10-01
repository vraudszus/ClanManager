import pandas as pd
import datetime
import numpy as np
import math
import yaml

from playerRanking import gsheetsApiWrapper
from playerRanking import crApiWrapper
from playerRanking import historyWrapper


def check_coefficients(rating_coefficients):
    rating_coefficients_list = list(rating_coefficients.values())
    if sum(rating_coefficients_list) != 1.0 or min(rating_coefficients_list) < 0:
        print("Error: Rating coefficients do not sum up to 1.0 or are negative.")
        exit()


def adjust_war_weights(rating_coefficients):
    now = datetime.datetime.utcnow()
    seconds_since_midnight = (
        now - now.replace(hour=10, minute=0, second=0, microsecond=0)).total_seconds()
    offset = (now.weekday() - 3) % 7
    # Find datetime for last Thursday 10:00 am UTC (roughly the begin of the war days)
    begin_of_war_days = now - \
        datetime.timedelta(days=offset, seconds=seconds_since_midnight)
    time_since_start = now - begin_of_war_days
    if time_since_start > datetime.timedelta(days=4):
        # Training days are currently happening, do not count current war
        war_progress = 0
        rating_coefficients["warHistoryCoefficient"] += rating_coefficients["currentWarCoefficient"]
        rating_coefficients["currentWarCoefficient"] = 0
    else:
        # War days are currently happening
        # Linearly increase weight for current war
        war_progress = time_since_start / \
            datetime.timedelta(days=4)  # ranges from 0 to 1
        rating_coefficients["warHistoryCoefficient"] += rating_coefficients["currentWarCoefficient"] * (
            1 - war_progress)
        rating_coefficients["currentWarCoefficient"] *= war_progress
    print("War progress:", war_progress)
    return (war_progress, rating_coefficients)


def ignoreSelectedWars(currentWar: pd.Series, warLog: pd.DataFrame, ignoreWars: list[str]):
    ignoredWarsInHistory = list(set(ignoreWars) & set(warLog.columns))
    warLog.loc[:, ignoredWarsInHistory] = np.nan
    if ignoreWars and max([float(i) for i in ignoreWars]) > float(warLog.columns[0]):
        currentWar.values[:] = 0
    return currentWar, warLog


def accountForShorterWars(warLog: pd.DataFrame, threeDayWars: list[str]):
    shorterWarsInHistory = list(set(threeDayWars) & set(warLog.columns))
    warLog.loc[:, shorterWarsInHistory] *= 4/3
    return warLog


def accept_excuses(service, current_war, war_log, members, valid_excuses, war_progress, gsheet_spreadsheet_id):
    excuses = gsheetsApiWrapper.get_excuses(
        "Abmeldungen", service, gsheet_spreadsheet_id)

    def handle_war(tag, war, fame):
        excuse = excuses.at[tag, war]
        if not math.isnan(fame) and excuse in valid_excuses.values():
            if excuse == valid_excuses["notInClanExcuse"] or excuse == valid_excuses["newPlayerExcuse"]:
                war_log.loc[tag, war] = np.nan
            else:
                war_log.loc[tag, war] = 1600
            print("Excuse accepted for", war, excuse, members[tag]["name"])

    def handle_current_war(tag):
        excuse = excuses.at[tag, "current"]
        if excuse in valid_excuses.values():
            if excuse == valid_excuses["newPlayerExcuse"]:
                current_war.at[tag] = np.nan
            else:
                current_war.at[tag] = 1600 * war_progress
            print("Excuse accepted for current CW:",
                  excuse, members[tag]["name"])

    for tag in members:
        if tag in excuses.index:
            handle_current_war(tag)
            if tag in war_log.index:
                for war, fame in war_log.loc[tag].items():
                    if war in excuses.columns:
                        handle_war(tag, war, fame)
    return current_war, war_log


def evaluate_performance(members, ladder, war_log, current_war, rating_coefficients, new_player_war_log_rating):
    current_season_max_trophies = ladder["current_season_best_trophies"].max()
    current_season_min_trophies = ladder["current_season_best_trophies"].min()
    current_season_trophy_range = current_season_max_trophies - \
        current_season_min_trophies
    previous_season_max_trophies = ladder["previous_season_best_trophies"].max(
    )
    previous_season_min_trophies = ladder["previous_season_best_trophies"].min(
    )
    previous_season_trophy_range = previous_season_max_trophies - \
        previous_season_min_trophies
    war_log["mean"] = war_log.mean(axis=1)
    war_log_max_fame = war_log["mean"].max()
    war_log_min_fame = war_log["mean"].min()
    war_history_fame_range = war_log_max_fame - war_log_min_fame
    current_max_fame = current_war.max()
    current_min_fame = current_war.min()
    current_fame_range = current_max_fame - current_min_fame

    cur_trophy_ranking = ladder["current_season_trophies"].sort_values(
        ascending=False)
    for i, row in enumerate(cur_trophy_ranking.items()):
        tag, _ = row
        cur_trophy_ranking[tag] = i+1

    for player_tag in members.keys():
        current_best_trophies = ladder.at[player_tag,
                                          "current_season_best_trophies"]
        current_ladder_rating = (
            current_best_trophies - current_season_min_trophies) / current_season_trophy_range
        previous_best_trophies = ladder.at[player_tag,
                                           "previous_season_best_trophies"]
        previous_ladder_rating = (
            previous_best_trophies - previous_season_min_trophies) / previous_season_trophy_range
        war_log_mean = war_log.at[player_tag,
                                  "mean"] if player_tag in war_log.index else None

        if not pd.isnull(war_log_mean):
            war_log_rating = (war_log_mean - war_log_min_fame) / \
                war_history_fame_range
        else:
            war_log_rating = None
        # player_tag is not present in current_war until a user has logged in after season reset
        current_fame = current_war[player_tag] if player_tag in current_war else 0
        if current_fame_range > 0:
            current_war_rating = (
                current_fame - current_min_fame) / current_fame_range
        else:
            # Default value that is used during trainings days.
            # Does not affect the rating on those days
            current_war_rating = 1

        members[player_tag]["rating"] = -1
        members[player_tag]["current_season"] = current_ladder_rating * 1000
        members[player_tag]["previous_season"] = previous_ladder_rating * 1000
        members[player_tag]["current_war"] = current_war_rating * 1000
        members[player_tag]["war_history"] = war_log_rating * \
            1000 if war_log_rating is not None else None
        members[player_tag]["avg_fame"] = war_log.at[player_tag,
                                                     "mean"] if player_tag in war_log.index else None
        members[player_tag]["ladder_rank"] = cur_trophy_ranking[player_tag]

        members[player_tag]["rating"] = (rating_coefficients["currentLadderCoefficient"] * members[player_tag]["current_season"]
                                         + rating_coefficients["previousLadderCoefficient"] * members[player_tag]["previous_season"]
                                         + rating_coefficients["currentWarCoefficient"] * members[player_tag]["current_war"])
        if members[player_tag]["war_history"] is not None:
            members[player_tag]["rating"] += rating_coefficients["warHistoryCoefficient"] * \
                members[player_tag]["war_history"]
        else:
            members[player_tag]["rating"] += rating_coefficients["warHistoryCoefficient"] * \
                new_player_war_log_rating

    performance = pd.DataFrame.from_dict(members, orient="index")

    print("Performance rating calculated according to the following formula:")
    print("rating =",
          "{:.2f}".format(
              rating_coefficients["currentLadderCoefficient"]), "* current_season +",
          "{:.2f}".format(
              rating_coefficients["previousLadderCoefficient"]), "* previous_season +",
          "{:.2f}".format(
              rating_coefficients["currentWarCoefficient"]), "* current_war +",
          "{:.2f}".format(rating_coefficients["warHistoryCoefficient"]), "* war_history")
    return performance.sort_values("rating", ascending=False)


def print_pending_rank_changes(members, war_log, requirements):
    war_log = war_log.copy()
    war_log = war_log.drop("mean", axis=1)
    min_fame = requirements["minFameForCountingWar"]
    min_wars = requirements["minCountingWars"]
    # promotions
    only_members = dict((k, v["name"]) for (
        k, v) in members.items() if v["role"] == "member")
    promotion_deserving_logs = war_log[war_log >= min_fame].count(
        axis="columns")
    promotion_deserving_logs = promotion_deserving_logs[promotion_deserving_logs >= min_wars]
    promotion_deserving_logs = promotion_deserving_logs[promotion_deserving_logs.index.isin(
        only_members.keys())]
    promotion_deserving_logs = list(
        promotion_deserving_logs.index.map(lambda k: only_members[k]))
    if promotion_deserving_logs:
        print("Pending promotions for:", ', '.join(promotion_deserving_logs))
    # demotions
    only_elders = dict((k, v["name"])
                       for (k, v) in members.items() if v["role"] == "elder")
    demotion_deserving_logs = war_log[war_log >=
                                      min_fame].count(axis="columns")
    demotion_deserving_logs = demotion_deserving_logs[demotion_deserving_logs < min_wars]
    demotion_deserving_logs = demotion_deserving_logs[demotion_deserving_logs.index.isin(
        only_elders.keys())]
    demotion_deserving_logs = list(
        demotion_deserving_logs.index.map(lambda k: only_elders[k]))
    if demotion_deserving_logs:
        print("Pending demotions for:", ', '.join(demotion_deserving_logs))


def perform_evaluation():
    props = yaml.safe_load(open("properties.yaml", "r"))
    clan_tag = props["clanTag"]
    cr_api_url = props["crApiUrl"]
    cr_token = props["apiTokens"]["crApiTokenPath"]
    gsheet_credentials = props["apiTokens"]["gsheetsCredentialsPath"]
    gsheet_token = props["apiTokens"]["gsheetsTokenPath"]
    rating_coefficients = props["ratingCoefficients"]
    new_player_war_log_rating = props["newPlayerWarLogRating"]
    valid_excuses = props["valid_excuses"]
    not_in_clan_excuse = valid_excuses["notInClanExcuse"]
    pro_demotion_requirements = props["promotion_demotion_requirements"]
    rating_file = props["ratingFile"]
    rating_history_file = props["ratingHistoryFile"]
    rating_history_image = props["ratingHistoryImage"]
    rating_gsheet = props["googleSheets"]["rating"]
    excuses_gsheet = props["googleSheets"]["excuses"]
    gsheet_spreadsheet_id = open(
        props["googleSheets"]["spreadsheetIdPath"], "r").read()
    ignoreWars = props["ignoreWars"]
    threeDayWars = props["threeDayWars"]

    check_coefficients(rating_coefficients)
    print(f"Evaluating performance of players from {clan_tag}...")
    members = crApiWrapper.get_current_members(clan_tag, cr_token, cr_api_url)
    war_log = crApiWrapper.get_war_statistics(
        clan_tag, members, cr_token, cr_api_url)
    current_war = crApiWrapper.get_current_river_race(
        clan_tag, cr_token, cr_api_url)
    ladder = crApiWrapper.get_ladder_statistics(members, cr_token, cr_api_url)

    service = gsheetsApiWrapper.connect_to_service(
        gsheet_credentials, gsheet_token)

    war_progress, rating_coefficients = adjust_war_weights(rating_coefficients)
    war_log = accountForShorterWars(war_log, threeDayWars)
    current_war, war_log = ignoreSelectedWars(
        current_war, war_log, ignoreWars)
    current_war, war_log = accept_excuses(
        service, current_war, war_log, members, valid_excuses, war_progress, gsheet_spreadsheet_id)
    performance = evaluate_performance(
        members, ladder, war_log, current_war, rating_coefficients, new_player_war_log_rating)

    historyWrapper.append_rating_history(
        rating_history_file, performance["rating"])
    historyWrapper.plot_rating_history(
        rating_history_file, members, rating_history_image)
    print_pending_rank_changes(members, war_log, pro_demotion_requirements)

    performance = performance.reset_index(drop=True)
    performance.index += 1
    performance.loc["mean"] = performance.iloc[:, 2:].mean()
    performance.loc["median"] = performance.iloc[:-1, 2:].median()
    performance.to_csv(rating_file, sep=";", float_format="%.0f")
    print(performance)

    gsheetsApiWrapper.write_df_to_sheet(
        performance, rating_gsheet, gsheet_spreadsheet_id, service)
    gsheetsApiWrapper.update_excuse_sheet(
        members, current_war, war_log, not_in_clan_excuse, excuses_gsheet, service, gsheet_spreadsheet_id)
