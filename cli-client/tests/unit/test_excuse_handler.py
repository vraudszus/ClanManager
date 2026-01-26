import math
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from player_ranking.excuse_handler import ExcuseHandler
from player_ranking.models.clan import Clan
from player_ranking.models.clan_member import ClanMember
from player_ranking.models.ranking_parameters import Excuses


def test_truncate():
    no_longer_present_player = pd.DataFrame(
        {
            "w0": ["a"],
            "w1": ["a"],
            "w2": ["a"],
            "w3": ["a"],
            "w4": ["a"],
            "w5": ["a"],
            "w6": ["a"],
            "w7": ["a"],
            "w8": ["a"],
            "w9": ["a"],
            "w10": ["a"],
        }
    )
    assert no_longer_present_player.shape == (1, 11)
    ExcuseHandler.truncate(no_longer_present_player, "a")
    assert no_longer_present_player.shape == (0, 11)

    one_war_too_many = pd.DataFrame(
        {
            "name": [""],
            "w0": [""],
            "w1": [""],
            "w2": [""],
            "w3": [""],
            "w4": [""],
            "w5": [""],
            "w6": [""],
            "w7": [""],
            "w8": [""],
            "w9": [""],
            "w10": [""],
            "w11": [""],
        }
    )
    assert one_war_too_many.shape == (1, 13)
    ExcuseHandler.truncate(one_war_too_many, "a")
    assert one_war_too_many.shape == (1, 12)
    assert "w11" not in one_war_too_many.columns

    unchanged = pd.DataFrame(
        {
            "w0": ["a"],
            "w1": ["a"],
            "w2": ["a"],
        }
    )
    assert unchanged.shape == (1, 3)
    ExcuseHandler.truncate(unchanged, "a")
    assert unchanged.shape == (1, 3)


def test_add_missing_wars():
    empty_excuses = pd.DataFrame({})
    empty_excuses_after = ExcuseHandler.add_missing_wars(
        empty_excuses, pd.Series([], name="100.1"), pd.DataFrame({"100.0": [], "99.4": []})
    )
    assert empty_excuses_after.columns.tolist() == ["name", "100.1", "100.0", "99.4"]

    identical_excuses = pd.DataFrame({"name": [], "100.1": []})
    identical_excuses_after = ExcuseHandler.add_missing_wars(
        identical_excuses, pd.Series([], name="100.1"), pd.DataFrame({})
    )
    assert identical_excuses_after.columns.tolist() == ["name", "100.1"]

    shift_by_one = pd.DataFrame({"name": [], "100.1": []})
    shift_by_one_after = ExcuseHandler.add_missing_wars(
        shift_by_one, pd.Series([], name="100.2"), pd.DataFrame({"100.1": []})
    )
    assert shift_by_one_after.columns.tolist() == ["name", "100.2", "100.1"]

    gap_in_data = pd.DataFrame({"name": [], "100.0": []})
    gap_in_data_after = ExcuseHandler.add_missing_wars(
        gap_in_data, pd.Series([], name="100.3"), pd.DataFrame({"100.2": []})
    )
    assert gap_in_data_after.columns.tolist() == ["name", "100.3", "100.2", "100.0"]


def test_update_current_war():
    clan = Clan()

    player_not_in_clan = pd.DataFrame({"name": ["player0"], "100.0": [""]}, index=["#0"])
    ExcuseHandler.update_current_war(player_not_in_clan, clan, pd.Series([], name="100.0"), "a")
    assert player_not_in_clan.loc["#0", "100.0"] == "a"

    clan.add(create_player("#1", "player1"))

    player_not_in_clan = pd.DataFrame({"name": ["player1"], "100.0": ["a"]}, index=["#1"])
    ExcuseHandler.update_current_war(player_not_in_clan, clan, pd.Series([], name="100.0"), "a")
    assert player_not_in_clan.loc["#1", "100.0"] == ""

    no_changes = pd.DataFrame({"name": ["player1"], "100.0": [""]}, index=["#1"])
    ExcuseHandler.update_current_war(no_changes, clan, pd.Series([], name="100.0"), "a")
    assert no_changes.loc["#1", "100.0"] == ""


def test_add_missing_players():
    clan = Clan()
    df = pd.DataFrame(
        {
            "name": ["player0", "player1", "player2"],
            "w0": ["", "", ""],
        },
        index=["#0", "#1", "#2"],
    )

    clan.add(create_player("#1", "player1"))
    clan.add(create_player("#2", "player2"))

    # all current players are already in df
    assert df.index.tolist() == ["#0", "#1", "#2"]
    ExcuseHandler.add_missing_players(df, clan)
    assert df.index.tolist() == ["#0", "#1", "#2"]

    clan.add(create_player("#2", "player2_new"))

    # all current players are already in df, but player2 has a new name
    assert df.index.tolist() == ["#0", "#1", "#2"]
    ExcuseHandler.add_missing_players(df, clan)
    assert df.index.tolist() == ["#0", "#1", "#2"]
    assert df.loc["#2"].tolist() == ["player2_new", ""]

    clan.add(create_player("#3", "player3"))

    # player is missing from df
    assert df.index.tolist() == ["#0", "#1", "#2"]
    ExcuseHandler.add_missing_players(df, clan)
    assert df.index.tolist() == ["#0", "#1", "#2", "#3"]
    assert df.loc["#3"].tolist() == ["player3", ""]


def test_format():
    df = pd.DataFrame(
        {
            "name": ["player3", "player1", "player2"],
            "w0": ["", "", ""],
        }
    )
    ExcuseHandler.format(df)
    assert df.index.name == "tag"
    assert df["name"].tolist() == ["player1", "player2", "player3"]


def test_update_excuses_basic_flow():
    """
    Testing:
    - adding missing wars
    - adding missing players
    - updating current war excuses
    - formatting (sorting + index name)
    """

    # existing excuses with one historical war
    excuses = pd.DataFrame(
        {
            "name": ["old_name"],
            "100.0": [""],
        },
        index=["#1"],
    )

    # clan has player #1 (with updated name) and a new player #2
    clan = Clan()
    clan.add(create_player("#1", "player1"))
    clan.add(create_player("#2", "player2"))

    # current war is newer than existing data
    current_war = pd.Series([], name="100.1")

    # war history includes one completed war
    war_history = pd.DataFrame({"100.0": []})

    params = Excuses(notInClanExcuse="NIC", newPlayerExcuse="NPE", personalExcuse="PE")

    handler = ExcuseHandler(excuses=excuses, clan=clan, excuse_params=params)

    handler.update_excuses(current_war=current_war, war_log=war_history)
    result = handler._excuses

    # index name set
    assert result.index.name == "tag"

    # wars are present and correctly ordered
    assert result.columns.tolist() == ["name", "100.1", "100.0"]

    # both players are present
    assert set(result.index) == {"#1", "#2"}

    # names updated from clan and sorted alphabetically
    assert result["name"].tolist() == ["player1", "player2"]

    # current war excuse is empty for clan members
    assert result.loc["#1", "100.1"] == ""
    assert result.loc["#2", "100.1"] == ""


def test_update_excuses_truncates_long_absent_player():
    """
    Testing:
    - current war update
    - player not in clan getting notInClanExcuse
    - truncation of players absent for >= 11 wars
    - truncation of old wars
    """

    # 11 historical wars where player was not in clan
    war_columns = {f"{100.0 - i}": ["NIC"] for i in range(10)}
    excuses = pd.DataFrame(
        {"name": ["former_player"], **war_columns},
        index=["#gone"],
    )

    clan = Clan()  # player is no longer in clan

    current_war = pd.Series([], name="100.1")
    war_history = pd.DataFrame({k: [] for k in war_columns})
    result = get_updated_excuses(
        old_excuses=excuses, clan=clan, current_war=current_war, war_history=war_history
    )

    # player is dropped entirely due to long absence
    assert result.empty


def test_update_excuses_does_not_modify_existing_war_columns():
    """
    Testing:
    - Only the current war column may be modified
    - All existing war columns remain unchanged
    """

    excuses = pd.DataFrame(
        {
            "name": ["player1", "player2"],
            "100.0": ["", "NIC"],  # historical war
            "99.9": ["x", ""],  # even older war
        },
        index=["#1", "#2"],
    )

    clan = Clan()
    clan.add(create_player("#1", "player1"))
    # player #2 is NOT in clan

    current_war = pd.Series([], name="100.1")
    war_history = pd.DataFrame({"100.0": [], "99.9": []})
    result = get_updated_excuses(
        old_excuses=excuses, clan=clan, current_war=current_war, war_history=war_history
    )

    # sanity: current war column added
    assert "100.1" in result.columns

    # historical columns must be unchanged
    assert result.loc["#1", "100.0"] == ""
    assert result.loc["#1", "99.9"] == "x"

    assert result.loc["#2", "100.0"] == "NIC"
    assert result.loc["#2", "99.9"] == ""

    # only current war is updated
    assert result.loc["#1", "100.1"] == ""
    assert result.loc["#2", "100.1"] == "NIC"


def test_update_excuses_with_empty_initial_dataframe():
    """
    Test ensuring update_excuses works correctly when starting from an empty excuses DataFrame.
    """

    excuses = pd.DataFrame()

    clan = Clan()
    clan.add(create_player("#1", "alice"))
    clan.add(create_player("#2", "bob"))

    current_war = pd.Series([], name="100.1")
    war_history = pd.DataFrame({"100.0": []})
    result = get_updated_excuses(
        old_excuses=excuses, clan=clan, current_war=current_war, war_history=war_history
    )

    # structure
    assert result.index.name == "tag"
    assert result.columns.tolist() == ["name", "100.1", "100.0"]

    # both clan members are present
    assert set(result.index) == {"#1", "#2"}

    # names populated and sorted
    assert result["name"].tolist() == ["alice", "bob"]

    # current war excuses are empty for clan members
    assert result.loc["#1", "100.1"] == ""
    assert result.loc["#2", "100.1"] == ""

    # historical war column exists and is empty
    assert result.loc["#1", "100.0"] == ""
    assert result.loc["#2", "100.0"] == ""


def test_get_new_fame_without_excuse_returns_old_fame():
    params = Excuses(notInClanExcuse="NIC", newPlayerExcuse="NPE", personalExcuse="PE")

    result = ExcuseHandler.get_new_fame(
        excuse_params=params,
        player_name="player1",
        excuse="",
        old_fame=1234,
        war_id="100.1",
    )

    assert result == 1234


def test_get_new_fame_nan_old_fame_is_preserved():
    params = Excuses(notInClanExcuse="NIC", newPlayerExcuse="NPE", personalExcuse="PE")

    result = ExcuseHandler.get_new_fame(
        excuse_params=params,
        player_name="player1",
        excuse="ANY",
        old_fame=np.nan,
        war_id="100.1",
    )

    assert math.isnan(result)


def test_get_new_fame_ignore_war_excuse_sets_nan():
    params = Excuses(notInClanExcuse="NIC", newPlayerExcuse="NPE", personalExcuse="PE")

    result = ExcuseHandler.get_new_fame(
        excuse_params=params,
        player_name="player1",
        excuse=params.notInClanExcuse,
        old_fame=1200,
        war_id="100.1",
    )

    assert pd.isna(result)


def test_get_new_fame_valid_excuse_sets_scaled_fame():
    params = Excuses(notInClanExcuse="NIC", newPlayerExcuse="NPE", personalExcuse="PE")

    result = ExcuseHandler.get_new_fame(
        excuse_params=params,
        player_name="player1",
        excuse=params.personalExcuse,
        old_fame=500,
        war_id="100.1",
        factor=0.5,
    )

    assert result == int(1600 * 0.5)


def test_get_new_fame_invalid_excuse_raises():
    params = Excuses(notInClanExcuse="NIC", newPlayerExcuse="NPE", personalExcuse="PE")

    with pytest.raises(Exception, match="Unknown excuse 'INVALID_EXCUSE' encountered."):
        ExcuseHandler.get_new_fame(
            excuse_params=params,
            player_name="player1",
            excuse="INVALID_EXCUSE",
            old_fame=1000,
            war_id="100.1",
        )


def test_adjust_fame_updates_only_excused_players_current_war():
    clan = Clan()
    clan.add(create_player("#1", "player1"))
    clan.add(create_player("#2", "player2"))

    params = Excuses(notInClanExcuse="NIC", newPlayerExcuse="NPE", personalExcuse="PE")

    excuses = pd.DataFrame(
        {
            "name": ["player1", "player2"],
            "100.1": [params.personalExcuse, ""],
        },
        index=["#1", "#2"],
    )

    current_war = pd.Series({"#1": 500, "#2": 800}, name="100.1")
    war_log = pd.DataFrame(index=["#1", "#2"])

    handler = ExcuseHandler(
        excuses=excuses,
        clan=clan,
        excuse_params=params,
    )

    handler.adjust_fame_with_excuses(current_war, war_log, war_progress=1.0)

    assert current_war["#1"] == 1600
    assert current_war["#2"] == 800


def test_adjust_fame_updates_war_log_history():
    clan = Clan()
    clan.add(create_player("#1", "player1"))

    params = Excuses(notInClanExcuse="NIC", newPlayerExcuse="NPE", personalExcuse="PE")

    excuses = pd.DataFrame(
        {
            "name": ["player1"],
            "100.1": [params.personalExcuse],
            "100.0": [params.personalExcuse],
        },
        index=["#1"],
    )

    current_war = pd.Series({"#1": 400}, name="100.1")
    war_log = pd.DataFrame({"100.0": [300]}, index=["#1"])

    handler = ExcuseHandler(
        excuses=excuses,
        clan=clan,
        excuse_params=params,
    )

    handler.adjust_fame_with_excuses(current_war, war_log, war_progress=1.0)

    assert current_war["#1"] == 1600
    assert war_log.loc["#1", "100.0"] == 1600


def test_adjust_fame_player_not_in_war_log_is_ignored():
    clan = Clan()
    clan.add(create_player("#1", "player1"))

    params = Excuses(notInClanExcuse="NIC", newPlayerExcuse="NPE", personalExcuse="PE")

    excuses = pd.DataFrame(
        {"name": ["player1"], "100.1": [params.personalExcuse]},
        index=["#1"],
    )

    current_war = pd.Series({"#1": 200}, name="100.1")
    war_log = pd.DataFrame()  # empty

    handler = ExcuseHandler(
        excuses=excuses,
        clan=clan,
        excuse_params=params,
    )

    handler.adjust_fame_with_excuses(current_war, war_log, war_progress=0.5)

    assert current_war["#1"] == int(1600 * 0.5)
    assert war_log.empty


def get_updated_excuses(
    old_excuses: pd.DataFrame, clan: Clan, current_war: pd.Series, war_history: pd.DataFrame
) -> pd.DataFrame:
    params = Excuses(notInClanExcuse="NIC", newPlayerExcuse="NPE", personalExcuse="PE")

    handler = ExcuseHandler(excuses=old_excuses, clan=clan, excuse_params=params)

    handler.update_excuses(current_war=current_war, war_log=war_history)
    return handler.get_excuses_as_df()

def create_player(tag: str, name: str) -> ClanMember:
    return ClanMember(tag, name, "member", 100, 50, 100, datetime(2026, 1, 26))
