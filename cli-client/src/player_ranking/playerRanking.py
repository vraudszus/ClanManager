import json
import logging
import os
import yaml

from player_ranking import crApiWrapper
from player_ranking import historyWrapper
from player_ranking.constants import ROOT_DIR
from player_ranking.evalutation_performer import EvaluationPerformer
from player_ranking.gsheetsApiWrapper import GSheetsWrapper

LOGGER = logging.getLogger(__name__)


def print_pending_rank_changes(members, war_log, requirements):
    war_log = war_log.copy()
    war_log = war_log.drop("mean", axis=1)
    min_fame = requirements["minFameForCountingWar"]
    min_wars = requirements["minCountingWars"]
    # promotions
    only_members = dict((k, v["name"]) for (k, v) in members.items() if v["role"] == "member")
    promotion_deserving_logs = war_log[war_log >= min_fame].count(axis="columns")
    promotion_deserving_logs = promotion_deserving_logs[promotion_deserving_logs >= min_wars]
    promotion_deserving_logs = promotion_deserving_logs[promotion_deserving_logs.index.isin(only_members.keys())]
    promotion_deserving_logs = list(promotion_deserving_logs.index.map(lambda k: only_members[k]))
    if promotion_deserving_logs:
        LOGGER.info(f"Pending promotions for: {', '.join(promotion_deserving_logs)}")
    # demotions
    only_elders = dict((k, v["name"]) for (k, v) in members.items() if v["role"] == "elder")
    demotion_deserving_logs = war_log[war_log >= min_fame].count(axis="columns")
    demotion_deserving_logs = demotion_deserving_logs[demotion_deserving_logs < min_wars]
    demotion_deserving_logs = demotion_deserving_logs[demotion_deserving_logs.index.isin(only_elders.keys())]
    demotion_deserving_logs = list(demotion_deserving_logs.index.map(lambda k: only_elders[k]))
    if demotion_deserving_logs:
        LOGGER.info(f"Pending demotions for: {', '.join(demotion_deserving_logs)}")


def perform_evaluation(plot: bool):
    props = yaml.safe_load(open(ROOT_DIR / "ranking_parameters.yaml", "r"))
    clan_tag = props["clanTag"]
    rating_coefficients = props["ratingWeights"]
    new_player_war_log_rating = props["newPlayerWarLogRating"]
    valid_excuses = props["excuses"]
    not_in_clan_excuse = valid_excuses["notInClanExcuse"]
    pro_demotion_requirements = props["promotionDemotionRequirements"]
    rating_file = props["ratingFile"]
    rating_history_file = props["ratingHistoryFile"]
    rating_history_image = props["ratingHistoryImage"]
    rating_gsheet = props["googleSheets"]["rating"]
    excuses_gsheet = props["googleSheets"]["excuses"]
    ignoreWars = props["ignoreWars"]
    threeDayWars = props["threeDayWars"]

    cr_api_token = os.getenv("CR_API_TOKEN")
    gsheets_refresh_token = json.loads(os.getenv("GSHEETS_REFRESH_TOKEN"))
    gsheets_spreadsheet_id = os.getenv("GSHEET_SPREADSHEET_ID")
    if not cr_api_token or not gsheets_refresh_token or not gsheets_spreadsheet_id:
        raise KeyError("Required secrets not found in environment.")

    LOGGER.info(f"Evaluating performance of players from {clan_tag}...")
    members = crApiWrapper.get_current_members(clan_tag, cr_api_token)
    war_log = crApiWrapper.get_war_statistics(clan_tag, members, cr_api_token)
    current_war = crApiWrapper.get_current_river_race(clan_tag, cr_api_token)
    path = crApiWrapper.get_path_statistics(members, cr_api_token)

    gSheetsWrapper = GSheetsWrapper(
        gsheets_refresh_token,
        gsheets_spreadsheet_id,
        ROOT_DIR,
    )
    excusesDf = gSheetsWrapper.get_excuses(excuses_gsheet)

    evaluationPerformer = EvaluationPerformer(members, current_war, war_log, path, rating_coefficients)
    evaluationPerformer.adjust_war_weights()
    evaluationPerformer.adjust_season_weights()
    evaluationPerformer.account_for_shorter_wars(threeDayWars)
    evaluationPerformer.ignore_selected_wars(ignoreWars)
    evaluationPerformer.accept_excuses(valid_excuses, excusesDf)
    performance = evaluationPerformer.evaluate_performance(new_player_war_log_rating)

    historyWrapper.append_rating_history(ROOT_DIR / rating_history_file, performance["rating"])
    if plot:
        historyWrapper.plot_rating_history(ROOT_DIR / rating_history_file, members, ROOT_DIR / rating_history_image)
    print_pending_rank_changes(members, war_log, pro_demotion_requirements)

    performance = performance.reset_index(drop=True)
    performance.index += 1
    performance.loc["mean"] = performance.iloc[:, 2:].mean()
    performance.loc["median"] = performance.iloc[:-1, 2:].median()
    performance.to_csv(ROOT_DIR / rating_file, sep=";", float_format="%.0f")
    print(performance)

    gSheetsWrapper.write_df_to_sheet(performance, rating_gsheet)
    gSheetsWrapper.update_excuse_sheet(members, current_war, war_log, not_in_clan_excuse, excuses_gsheet)
