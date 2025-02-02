import json
import logging
import os

from player_ranking import crApiWrapper
from player_ranking import historyWrapper
from player_ranking.constants import ROOT_DIR
from player_ranking.evalutation_performer import EvaluationPerformer
from player_ranking.gsheetsApiWrapper import GSheetsWrapper
from player_ranking.ranking_parameters import RankingParameters, PromotionDemotionRequirements
from player_ranking.ranking_parameters_validation import RankingParameterValidator

LOGGER = logging.getLogger(__name__)


def print_pending_rank_changes(members, war_log, requirements: PromotionDemotionRequirements):
    war_log = war_log.copy()
    war_log = war_log.drop("mean", axis=1)
    min_fame = requirements.minFameForCountingWar
    min_wars = requirements.minCountingWars
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
    params: RankingParameters = RankingParameterValidator(open(ROOT_DIR / "ranking_parameters.yaml")).validate()

    cr_api_token = read_env_variable("CR_API_TOKEN")
    gsheets_refresh_token_raw = read_env_variable("GSHEETS_REFRESH_TOKEN")
    gsheets_spreadsheet_id = read_env_variable("GSHEET_SPREADSHEET_ID")
    gsheets_refresh_token = json.loads(gsheets_refresh_token_raw)

    LOGGER.info(f"Evaluating performance of players from {params.clanTag}...")
    members = crApiWrapper.get_current_members(params.clanTag, cr_api_token)
    war_log = crApiWrapper.get_war_statistics(params.clanTag, members, cr_api_token)
    current_war = crApiWrapper.get_current_river_race(params.clanTag, cr_api_token)
    path = crApiWrapper.get_path_statistics(members, cr_api_token)

    gsheets_wrapper = GSheetsWrapper(
        refresh_token=gsheets_refresh_token,
        spreadsheet_id=gsheets_spreadsheet_id,
        sheet_names=params.googleSheets,
    )
    excuses_df = gsheets_wrapper.get_excuses()

    performance = EvaluationPerformer(members, current_war, war_log, path, params, excuses_df).evaluate()

    historyWrapper.append_rating_history(ROOT_DIR / params.ratingHistoryFile, performance["rating"])
    if plot:
        historyWrapper.plot_rating_history(
            ROOT_DIR / params.ratingHistoryFile, members, ROOT_DIR / params.ratingHistoryImage
        )
    print_pending_rank_changes(members, war_log, params.promotionDemotionRequirements)

    performance = performance.reset_index(drop=True)
    performance.index += 1
    performance.loc["mean"] = performance.iloc[:, 2:].mean()
    performance.loc["median"] = performance.iloc[:-1, 2:].median()
    performance.to_csv(ROOT_DIR / params.ratingFile, sep=";", float_format="%.0f")
    print(performance)

    gsheets_wrapper.write_sheet(performance, params.googleSheets.rating)
    gsheets_wrapper.update_excuse_sheet(members, current_war, war_log, params.excuses.notInClanExcuse)


def read_env_variable(env_var: str) -> str:
    var = os.getenv(env_var)
    if not var:
        raise EnvironmentError(
            f"The environment variable '{env_var}' is missing. Please check the README.md for how to configure it."
        )
    return var
