import pandas as pd
import pytest
import requests
from requests_mock.mocker import Mocker

from player_ranking.cr_api_client import CRAPIClient, url_encode
from player_ranking.models.clan import Clan
from player_ranking.models.clan_member import ClanMember

API_TOKEN: str = "1234567"
CLAN_TAG: str = "#ABCDEF"


@pytest.fixture
def cr_api_client() -> CRAPIClient:
    return CRAPIClient(API_TOKEN, CLAN_TAG)


@pytest.fixture
def clan() -> Clan:
    clan = Clan()
    clan.add(ClanMember("#1", "player1", "member", 100))
    clan.add(ClanMember("#2", "player2", "elder", 200))
    return clan


def test_url_encode():
    assert url_encode(CLAN_TAG) == "%23ABCDEF"


def test_get_current_members(requests_mock: Mocker, cr_api_client: CRAPIClient):
    mock_url = "https://proxy.royaleapi.dev/v1/clans/%23ABCDEF"
    mock_response = {
        "memberList": [
            {
                "tag": "#1",
                "name": "player1",
                "role": "member",
                "trophies": 100,
            },
            {
                "tag": "#2",
                "name": "player2",
                "role": "elder",
                "trophies": 200,
            },
        ]
    }
    requests_mock.get(mock_url, json=mock_response, status_code=200)

    members = cr_api_client.get_current_members().get_members()
    assert len(members) == 2
    assert members[0].tag == "#1"
    assert members[0].name == "player1"
    assert members[0].role == "member"
    assert members[0].trophies == 100
    assert members[1].tag == "#2"
    assert members[1].name == "player2"
    assert members[1].role == "elder"
    assert members[1].trophies == 200


def test_get_current_riverrace(requests_mock: Mocker, cr_api_client: CRAPIClient):
    mock_url = "https://proxy.royaleapi.dev/v1/clans/%23ABCDEF/currentriverrace"
    mock_response = {
        "clan": {
            "participants": [
                {"tag": "#1", "fame": 100},
                {"tag": "#2", "fame": 200},
            ]
        }
    }
    requests_mock.get(mock_url, json=mock_response, status_code=200)
    current_war = cr_api_client.get_current_river_race()
    pd.testing.assert_series_equal(current_war, pd.Series({"#1": 100, "#2": 200}))


def test_get_war_statistics(requests_mock: Mocker, cr_api_client: CRAPIClient, clan: Clan):
    mock_url = "https://proxy.royaleapi.dev/v1/clans/%23ABCDEF/riverracelog"
    mock_response = {
        "items": [
            {
                "seasonId": 1,
                "sectionIndex": 2,
                "standings": [
                    {"clan": {"tag": "#OTHER_CLAN", "participants": [{"tag": "#OTHER_PLAYER", "fame": 10}]}},
                    {
                        "clan": {
                            "tag": "#ABCDEF",
                            "participants": [
                                {"tag": "#1", "fame": 100},
                                {"tag": "#2", "fame": 200},
                            ],
                        }
                    },
                ],
            },
            {
                "seasonId": 2,
                "sectionIndex": 3,
                "standings": [
                    {"clan": {"tag": "#OTHER_CLAN", "participants": [{"tag": "#OTHER_PLAYER", "fame": 20}]}},
                    {
                        "clan": {
                            "tag": "#ABCDEF",
                            "participants": [
                                {"tag": "#1", "fame": 200},
                                {"tag": "#3", "fame": 300},
                            ],
                        }
                    },
                ],
            },
        ]
    }
    requests_mock.get(mock_url, json=mock_response, status_code=200)
    war_log = cr_api_client.get_war_statistics(clan)

    # non-current members aren't included, while current members have null for wars they didn't participate in
    pd.testing.assert_frame_equal(
        war_log,
        pd.DataFrame({"2.3": [200.0, None], "1.2": [100, 200]}, index=["#1", "#2"]),
    )


def test_get_path_statistics(requests_mock: Mocker, cr_api_client: CRAPIClient, clan: Clan):
    mock_url = "https://proxy.royaleapi.dev/v1/players/%23"
    mock_response1 = {
        "currentPathOfLegendSeasonResult": {"leagueNumber": 8, "trophies": 0},
        "lastPathOfLegendSeasonResult": {"leagueNumber": 10, "trophies": 100},
    }
    requests_mock.get(mock_url + "1", json=mock_response1, status_code=200)
    mock_response2 = {
        "currentPathOfLegendSeasonResult": {"leagueNumber": 2, "trophies": 0},
        "lastPathOfLegendSeasonResult": {"leagueNumber": 1, "trophies": 0},
    }
    requests_mock.get(mock_url + "2", json=mock_response2, status_code=200)

    cr_api_client.get_path_statistics(clan)
    members = clan.get_members()
    assert len(members) == 2
    assert members[0].tag == "#1"
    assert members[0].current_season_league_number == 8
    assert members[0].current_season_trophies == 0
    assert members[0].previous_season_league_number == 10
    assert members[0].previous_season_trophies == 100
    assert members[1].tag == "#2"
    assert members[1].current_season_league_number == 2
    assert members[1].current_season_trophies == 0
    assert members[1].previous_season_league_number == 1
    assert members[1].previous_season_trophies == 0


def test_get_current_members_fails(requests_mock: Mocker, cr_api_client: CRAPIClient):
    expected_headers = {"Accept": "application/json", "authorization": f"Bearer {API_TOKEN}"}
    mock_url = "https://proxy.royaleapi.dev/v1/clans/%23ABCDEF"
    requests_mock.get(mock_url, status_code=404)

    with pytest.raises(requests.exceptions.HTTPError) as exc_info:
        cr_api_client.get_current_members()

    assert exc_info.value.response.status_code == 404
    assert str(exc_info.value) == f"404 Client Error: None for url: {mock_url}"

    assert len(requests_mock.request_history) == 1
    actual_headers = requests_mock.request_history[0].headers
    assert actual_headers["Accept"] == expected_headers["Accept"]
    assert actual_headers["authorization"] == expected_headers["authorization"]
