import logging
import os

from player_ranking import history_wrapper
from player_ranking.constants import ROOT_DIR
from player_ranking.cr_api_client import CRAPIClient
from player_ranking.evaluation_performer import EvaluationPerformer
from player_ranking.gsheets_api_client import GSheetsAPIClient
from player_ranking.models.clan import Clan
from player_ranking.models.ranking_parameters import RankingParameters, PromotionDemotionRequirements
from player_ranking.models.ranking_parameters_validation import RankingParameterValidator

LOGGER = logging.getLogger(__name__)


def print_pending_rank_changes(clan: Clan, war_log, requirements: PromotionDemotionRequirements):
    war_log = war_log.copy()
    war_log = war_log.drop("mean", axis=1)
    min_fame = requirements.minFameForCountingWar
    min_wars = requirements.minCountingWars
    # promotions
    only_members = clan.filter(lambda member: member.role == "member")
    promotion_deserving_logs = war_log[war_log >= min_fame].count(axis="columns")
    promotion_deserving_logs = promotion_deserving_logs[promotion_deserving_logs >= min_wars]
    promotion_deserving_logs = promotion_deserving_logs[promotion_deserving_logs.index.isin(only_members.get_tags())]
    promotion_deserving_logs = list(promotion_deserving_logs.index.map(lambda k: only_members.get(k).name))
    if promotion_deserving_logs:
        LOGGER.info(f"Pending promotions for: {', '.join(promotion_deserving_logs)}")
    # demotions
    only_elders = clan.filter(lambda member: member.role == "elder")
    demotion_deserving_logs = war_log[war_log >= min_fame].count(axis="columns")
    demotion_deserving_logs = demotion_deserving_logs[demotion_deserving_logs < min_wars]
    demotion_deserving_logs = demotion_deserving_logs[demotion_deserving_logs.index.isin(only_elders.get_tags())]
    demotion_deserving_logs = list(demotion_deserving_logs.index.map(lambda k: only_elders.get(k).name))
    if demotion_deserving_logs:
        LOGGER.info(f"Pending demotions for: {', '.join(demotion_deserving_logs)}")


def perform_evaluation(plot: bool):
    params: RankingParameters = RankingParameterValidator(open(ROOT_DIR / "ranking_parameters.yaml")).validate()

    cr_api_token: str = read_env_variable("CR_API_TOKEN")
    gsheets_spreadsheet_id: str = read_env_variable("GSHEET_SPREADSHEET_ID")
    gsheets_refresh_token: str = read_env_variable("GSHEETS_REFRESH_TOKEN")

    LOGGER.info(f"Evaluating performance of players from {params.clanTag}...")
    cr_api = CRAPIClient(cr_api_token, params.clanTag)
    clan = cr_api.get_current_members()
    war_log = cr_api.get_war_statistics(clan)
    current_war = cr_api.get_current_river_race()
    cr_api.get_path_statistics(clan)

    gsheets_client = GSheetsAPIClient(
        refresh_token=gsheets_refresh_token,
        spreadsheet_id=gsheets_spreadsheet_id,
        sheet_names=params.googleSheets,
    )
    excuses_df = gsheets_client.get_excuses()

    performance = EvaluationPerformer(clan, current_war, war_log, params, excuses_df).evaluate()

    history_wrapper.append_rating_history(ROOT_DIR / params.ratingHistoryFile, performance["rating"])
    if plot:
        history_wrapper.plot_rating_history(
            ROOT_DIR / params.ratingHistoryFile, clan, ROOT_DIR / params.ratingHistoryImage
        )
    print_pending_rank_changes(clan, war_log, params.promotionDemotionRequirements)

    performance = performance.reset_index(drop=True)
    performance.index += 1
    performance.loc["mean"] = performance.iloc[:, 2:].mean()
    performance.loc["median"] = performance.iloc[:-1, 2:].median()
    performance.to_csv(ROOT_DIR / params.ratingFile, sep=";", float_format="%.0f")
    print(performance)

    gsheets_client.write_sheet(performance, params.googleSheets.rating)
    gsheets_client.update_excuse_sheet(clan, current_war, war_log, params.excuses.notInClanExcuse)


def read_env_variable(env_var: str) -> str:
    var = os.getenv(env_var)
    if not var:
        raise EnvironmentError(
            f"The environment variable '{env_var}' is missing. Please check the README.md for how to configure it."
        )
    return var
