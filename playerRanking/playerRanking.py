import yaml

from playerRanking.evalutation_performer import EvaluationPerformer
from playerRanking.gsheetsApiWrapper import GSheetsWrapper
from playerRanking import crApiWrapper
from playerRanking import historyWrapper


def check_coefficients(rating_coefficients):
    rating_coefficients_list = list(rating_coefficients.values())
    if sum(rating_coefficients_list) != 1.0 or min(rating_coefficients_list) < 0:
        print("Error: Rating coefficients do not sum up to 1.0 or are negative.")
        exit()


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


def perform_evaluation(plot: bool):
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
    spreadsheet_id_path = props["googleSheets"]["spreadsheetIdPath"]
    ignoreWars = props["ignoreWars"]
    threeDayWars = props["threeDayWars"]

    check_coefficients(rating_coefficients)
    print(f"Evaluating performance of players from {clan_tag}...")
    members = crApiWrapper.get_current_members(clan_tag, cr_token, cr_api_url)
    war_log = crApiWrapper.get_war_statistics(
        clan_tag, members, cr_token, cr_api_url)
    current_war = crApiWrapper.get_current_river_race(
        clan_tag, cr_token, cr_api_url)

    gSheetsWrapper = GSheetsWrapper(gsheet_credentials, gsheet_token, spreadsheet_id_path)
    excusesDf = gSheetsWrapper.get_excuses(excuses_gsheet)

    evaluationPerformer = EvaluationPerformer(members, current_war, war_log)
    evaluationPerformer.adjust_war_weights(rating_coefficients)
    evaluationPerformer.account_for_shorter_wars(threeDayWars)
    evaluationPerformer.ignore_selected_wars(ignoreWars)
    evaluationPerformer.accept_excuses(valid_excuses, excusesDf)
    performance = evaluationPerformer.evaluate_performance(new_player_war_log_rating)

    historyWrapper.append_rating_history(rating_history_file, performance["rating"])
    if plot:
        historyWrapper.plot_rating_history(
            rating_history_file, members, rating_history_image)
    print_pending_rank_changes(members, war_log, pro_demotion_requirements)

    performance = performance.reset_index(drop=True)
    performance.index += 1
    performance.loc["mean"] = performance.iloc[:, 2:].mean()
    performance.loc["median"] = performance.iloc[:-1, 2:].median()
    performance.to_csv(rating_file, sep=";", float_format="%.0f")
    print(performance)

    gSheetsWrapper.write_df_to_sheet(performance, rating_gsheet)
    gSheetsWrapper.update_excuse_sheet(
        members, current_war, war_log, not_in_clan_excuse, excuses_gsheet)
    input()  # keep cli window open
