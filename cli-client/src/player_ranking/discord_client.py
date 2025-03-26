import logging

import requests

from player_ranking.models.clan_member import ClanMember
from player_ranking.models.ranking_parameters import PromotionRequirements

LOGGER = logging.getLogger(__name__)
CLAN_WARS_ICON_URL = "https://static.wikia.nocookie.net/clashroyale/images/9/9f/War_Shield.png/revision/latest"
ELITE_BARBS_ICON_URL = (
    "https://static.wikia.nocookie.net/clashroyale/images/e/e8/EliteBarbariansCard.png/revision/latest"
)


class DiscordClient:
    def __init__(self, webhook: str):
        self.webhook = webhook

    def post_pending_promotions(
        self, requirements: PromotionRequirements, pending_promotions: list[ClanMember]
    ) -> None:
        LOGGER.info("Posting pending promotion message to webhook.")

        min_fame = requirements.minFameForCountingWar
        min_wars = requirements.minCountingWars
        requirements_msg = (
            f"To be recommended for promotion, a player must score at least **{min_fame} fame** "
            f"in **{min_wars} or more recent clan wars**."
        )
        players = [f"**{p.name}** ({p.tag})" for p in pending_promotions]

        message = {
            "username": "Clan Herald",
            "avatar_url": CLAN_WARS_ICON_URL,
            "embeds": [
                {
                    "title": "🎖️ Promotion Announcement",
                    "description": "The following players have earned a promotion to the rank of **Elder**:",
                    "color": 0xFFD700,
                    "fields": [
                        {
                            "name": "🏅 Up for Promotion",
                            "value": "\n".join(players),
                            "inline": False,
                        },
                        {
                            "name": "📋 Promotion Criteria",
                            "value": requirements_msg,
                            "inline": False,
                        },
                    ],
                    "footer": {
                        "text": "Keep up the great work!",
                        "icon_url": ELITE_BARBS_ICON_URL,
                    },
                }
            ],
        }
        response = requests.post(self.webhook, json=message)
        response.raise_for_status()
