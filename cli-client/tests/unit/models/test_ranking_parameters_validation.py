from typing import Any

import pytest
import yaml
from jsonschema import ValidationError

from player_ranking.models.ranking_parameters_validation import RankingParameterValidator


@pytest.fixture
def minimal_yaml_as_dict() -> dict[str, Any]:
    return {
        "clanTag": "#ABCDEF",
        "ratingWeights": {
            "ladder": 1,
            "warHistory": 0,
            "currentWar": 0,
            "previousSeasonLeague": 0,
            "previousSeasonTrophies": 0,
            "currentSeasonLeague": 0,
            "currentSeasonTrophies": 0,
        },
        "newPlayerWarRating": 500,
        "promotionRequirements": {
            "minFameForCountingWar": 2000,
            "minCountingWars": 5,
        },
        "excuses": {
            "notInClanExcuse": "excuse1",
            "newPlayerExcuse": "excuse2",
            "personalExcuse": "excuse3",
        },
        "googleSheets": {
            "rating": "sheet1",
            "excuses": "sheet2",
        },
        "ratingFile": "file1",
        "ratingHistoryFile": "file2",
        "ratingHistoryImage": "file3",
        "ignoreWars": [],
        "threeDayWars": [],
    }


def test_validate_with_empty_string_fails():
    param_yaml = ""
    with pytest.raises(ValidationError) as exc_info:
        RankingParameterValidator(param_yaml).validate()
    assert "None is not of type 'object" in str(exc_info.value)


def test_validate_with_invalid_yaml_fails():
    param_yaml = "missing_colon 1"
    with pytest.raises(ValidationError) as exc_info:
        RankingParameterValidator(param_yaml).validate()
    assert "'missing_colon 1' is not of type 'object'" in str(exc_info.value)


def test_validate_with_unknown_property_fails():
    param_yaml = "unknown_prop: 1"
    with pytest.raises(ValidationError) as exc_info:
        RankingParameterValidator(param_yaml).validate()
    assert "'clanTag' is a required property" in str(exc_info.value)


def test_validate_with_minimal_yaml_succeeds(minimal_yaml_as_dict):
    actual = RankingParameterValidator(yaml.dump(minimal_yaml_as_dict)).validate()

    assert actual.clanTag == minimal_yaml_as_dict["clanTag"]

    expected_weights = minimal_yaml_as_dict["ratingWeights"]
    assert actual.ratingWeights.ladder == expected_weights["ladder"]
    assert actual.ratingWeights.warHistory == expected_weights["warHistory"]
    assert actual.ratingWeights.currentWar == expected_weights["currentWar"]
    assert actual.ratingWeights.previousSeasonLeague == expected_weights["previousSeasonLeague"]
    assert actual.ratingWeights.previousSeasonTrophies == expected_weights["previousSeasonTrophies"]
    assert actual.ratingWeights.currentSeasonLeague == expected_weights["currentSeasonLeague"]
    assert actual.ratingWeights.currentSeasonTrophies == expected_weights["currentSeasonTrophies"]

    assert actual.newPlayerWarRating == minimal_yaml_as_dict["newPlayerWarRating"]

    expected_requirements = minimal_yaml_as_dict["promotionRequirements"]
    assert (
        actual.promotionRequirements.minFameForCountingWar
        == expected_requirements["minFameForCountingWar"]
    )
    assert actual.promotionRequirements.minCountingWars == expected_requirements["minCountingWars"]

    expected_excuses = minimal_yaml_as_dict["excuses"]
    assert actual.excuses.notInClanExcuse == expected_excuses["notInClanExcuse"]
    assert actual.excuses.newPlayerExcuse == expected_excuses["newPlayerExcuse"]
    assert actual.excuses.personalExcuse == expected_excuses["personalExcuse"]

    expected_sheets = minimal_yaml_as_dict["googleSheets"]
    assert actual.googleSheets.rating == expected_sheets["rating"]
    assert actual.googleSheets.excuses == expected_sheets["excuses"]

    assert actual.ratingFile == minimal_yaml_as_dict["ratingFile"]
    assert actual.ratingHistoryFile == minimal_yaml_as_dict["ratingHistoryFile"]
    assert actual.ratingHistoryImage == minimal_yaml_as_dict["ratingHistoryImage"]
    assert actual.ignoreWars == minimal_yaml_as_dict["ignoreWars"]
    assert actual.threeDayWars == minimal_yaml_as_dict["threeDayWars"]


def test_validate_with_invalid_clantag_fails(minimal_yaml_as_dict):
    minimal_yaml_as_dict["clanTag"] = "ABCDEF"
    with pytest.raises(ValidationError) as exc_info:
        RankingParameterValidator(yaml.dump(minimal_yaml_as_dict)).validate()
    assert "'ABCDEF' does not match '#[0-9A-Z]+'" in str(exc_info.value)


def test_validate_with_invalid_rating_weights_fails(minimal_yaml_as_dict):
    minimal_yaml_as_dict["ratingWeights"]["unknownWeight"] = 1
    with pytest.raises(ValidationError) as exc_info:
        RankingParameterValidator(yaml.dump(minimal_yaml_as_dict)).validate()
    assert "Additional properties are not allowed ('unknownWeight' was unexpected)" in str(
        exc_info.value
    )
    del minimal_yaml_as_dict["ratingWeights"]["unknownWeight"]

    minimal_yaml_as_dict["ratingWeights"]["ladder"] = 0.9
    with pytest.raises(ValueError) as exc_info:
        RankingParameterValidator(yaml.dump(minimal_yaml_as_dict)).validate()
    assert "Sum of ratingWeights must be 1." in str(exc_info.value)

    minimal_yaml_as_dict["ratingWeights"]["ladder"] = -0.1
    with pytest.raises(ValidationError) as exc_info:
        RankingParameterValidator(yaml.dump(minimal_yaml_as_dict)).validate()
    assert "-0.1 is less than the minimum of 0" in str(exc_info.value)

    del minimal_yaml_as_dict["ratingWeights"]["ladder"]
    with pytest.raises(ValidationError) as exc_info:
        RankingParameterValidator(yaml.dump(minimal_yaml_as_dict)).validate()
    assert "'ladder' is a required property" in str(exc_info.value)


def test_validate_with_special_wars_succeeds(minimal_yaml_as_dict):
    minimal_yaml_as_dict["ignoreWars"] = ["1.4"]
    minimal_yaml_as_dict["threeDayWars"] = ["1.4", "11.0"]
    actual = RankingParameterValidator(yaml.dump(minimal_yaml_as_dict)).validate()
    assert actual.ignoreWars == ["1.4"]
    assert actual.threeDayWars == ["1.4", "11.0"]


def test_validate_with_invalid_special_wars_fails(minimal_yaml_as_dict):
    minimal_yaml_as_dict["threeDayWars"] = ["1.5"]
    with pytest.raises(ValidationError) as exc_info:
        RankingParameterValidator(yaml.dump(minimal_yaml_as_dict)).validate()
    assert "'1.5' does not match '[0-9]+\\\\.[0-4]'" in str(exc_info.value)
