import logging
import os

from player_ranking import history_wrapper
from player_ranking.constants import ROOT_DIR
from player_ranking.cr_api_client import CRAPIClient
from player_ranking.discord_client import DiscordClient
from player_ranking.evaluation_performer import EvaluationPerformer
from player_ranking.excuse_handler import ExcuseHandler
from player_ranking.gsheets_api_client import GSheetsAPIClient
from player_ranking.models.clan import Clan
from player_ranking.models.clan_member import ClanMember
from player_ranking.models.ranking_parameters import RankingParameters, PromotionRequirements
from player_ranking.models.ranking_parameters_validation import RankingParameterValidator

LOGGER = logging.getLogger(__name__)


def get_pending_promotions(
    clan: Clan, war_log, requirements: PromotionRequirements
) -> list[ClanMember]:
    war_log = war_log.copy()
    war_log = war_log.drop("mean", axis=1)
    min_fame = requirements.minFameForCountingWar
    min_wars = requirements.minCountingWars

    only_members = clan.filter(lambda member: member.role == "member")
    promotion_deserving_logs = war_log[war_log >= min_fame].count(axis="columns")
    promotion_deserving_logs = promotion_deserving_logs[promotion_deserving_logs >= min_wars]
    promotion_deserving_logs = promotion_deserving_logs[
        promotion_deserving_logs.index.isin(only_members.get_tags())
    ]
    pending_promotions = promotion_deserving_logs.index.map(lambda k: only_members.get(k)).to_list()
    if pending_promotions:
        LOGGER.info(f"Pending promotions for: {', '.join([p.name for p in pending_promotions])}")
    else:
        LOGGER.info("No promotions pending.")
    return pending_promotions


def perform_evaluation(plot: bool):
    params: RankingParameters = RankingParameterValidator(
        open(ROOT_DIR / "ranking_parameters.yaml")
    ).validate()

    cr_api_token: str = read_env_variable("CR_API_TOKEN")
    gsheets_spreadsheet_id: str = read_env_variable("GSHEET_SPREADSHEET_ID")
    gsheets_service_account_key: str = read_env_variable("GSHEETS_SERVICE_ACCOUNT_KEY")
    discord_webhook: str = read_env_variable("DISCORD_WEBHOOK")

    LOGGER.info(f"Evaluating performance of players from {params.clanTag}...")
    cr_api = CRAPIClient(cr_api_token, params.clanTag)
    clan = cr_api.get_current_members()
    war_log = cr_api.get_war_statistics(clan)
    current_war = cr_api.get_current_river_race(war_log.columns[0])
    cr_api.get_path_statistics(clan)

    gsheets_client = GSheetsAPIClient(
        service_account_key=gsheets_service_account_key,
        spreadsheet_id=gsheets_spreadsheet_id,
    )
    excuses_df = gsheets_client.fetch_sheet(sheet_name=params.googleSheets.excuses)
    excuses = ExcuseHandler(excuses=excuses_df, clan=clan, excuse_params=params.excuses)
    excuses.update_excuses(current_war=current_war, war_log=war_log)

    performance = EvaluationPerformer(clan, current_war, war_log, params, excuses).evaluate()

    history_wrapper.append_rating_history(
        ROOT_DIR / params.ratingHistoryFile, performance["rating"]
    )
    if plot:
        history_wrapper.plot_rating_history(
            ROOT_DIR / params.ratingHistoryFile, clan, ROOT_DIR / params.ratingHistoryImage
        )
    pending_promotions: list[ClanMember] = get_pending_promotions(
        clan, war_log, params.promotionRequirements
    )
    if pending_promotions:
        DiscordClient(discord_webhook).post_pending_promotions(
            params.promotionRequirements, pending_promotions
        )

    performance = performance.reset_index(drop=True)
    performance.index += 1
    performance.loc["mean"] = performance.iloc[:, 1:-1].mean()
    performance.loc["p75"] = performance.iloc[:, 1:-1].quantile(0.75)
    performance.loc["p50"] = performance.iloc[:, 1:-1].quantile(0.50)
    performance.loc["p25"] = performance.iloc[:, 1:-1].quantile(0.25)
    performance.to_csv(ROOT_DIR / params.ratingFile, sep=";", float_format="%.0f")
    print(performance)

    gsheets_client.write_sheet(df=performance, sheet_name=params.googleSheets.rating)
    gsheets_client.write_sheet(
        df=excuses.get_excuses_as_df(), sheet_name=params.googleSheets.excuses
    )


def read_env_variable(env_var: str) -> str:
    var = os.getenv(env_var)
    if not var:
        raise EnvironmentError(
            f"The environment variable '{env_var}' is missing. Please check the README.md for how to configure it."
        )
    return var
