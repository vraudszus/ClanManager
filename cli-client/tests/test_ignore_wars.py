from playerRanking.playerRanking import ignoreSelectedWars
import pandas as pd
import numpy as np


def givenSimpleWarHistory() -> tuple[dict, dict]:
    currentWar = {
        "a": 100,
        "b": 200,
        "c": 0,
    }
    warLog = {
        "a": {
            "20.1": 300,
            "20.0": 400,
            "19.4": 500,
        },
        "b": {
            "20.1": 200,
            "19.4": 300,
        },
        "c": {},
    }
    return currentWar, warLog


def test_ignoreSelectedWars_ignoreNothing():
    currentWar, warLog = givenSimpleWarHistory()
    currentWarActual, warLogActual = ignoreSelectedWars(
        pd.Series(currentWar), pd.DataFrame.from_dict(warLog, orient="index"), []
    )

    assert pd.DataFrame.equals(pd.DataFrame.from_dict(warLog, orient="index"), warLogActual)
    assert pd.Series.equals(pd.Series(currentWar), currentWarActual)


def test_ignoreSelectedWars_ignoreOnlyCurrentWar():
    currentWar, warLog = givenSimpleWarHistory()
    currentWarActual, warLogActual = ignoreSelectedWars(
        pd.Series(currentWar), pd.DataFrame.from_dict(warLog, orient="index"), ["20.2"]
    )
    currentWarExpected = pd.Series(
        {
            "a": 0,
            "b": 0,
            "c": 0,
        }
    )
    assert pd.DataFrame.equals(pd.DataFrame.from_dict(warLog, orient="index"), warLogActual)
    assert pd.Series.equals(currentWarExpected, currentWarActual)


def test_ignoreSelectedWars_secondInHistory():
    currentWar, warLog = givenSimpleWarHistory()
    currentWarActual, warLogActual = ignoreSelectedWars(
        pd.Series(currentWar), pd.DataFrame.from_dict(warLog, orient="index"), ["20.0"]
    )
    warLogExpected = pd.DataFrame.from_dict(
        {
            "a": {
                "20.1": 300,
                "20.0": np.nan,
                "19.4": 500,
            },
            "b": {
                "20.1": 200,
                "19.4": 300,
            },
            "c": {},
        },
        orient="index",
    )
    assert pd.DataFrame.equals(warLogExpected, warLogActual)
    assert pd.Series.equals(pd.Series(currentWar), currentWarActual)


def test_ignoreSelectedWars_allIncludingOutdatedWars():
    currentWar, warLog = givenSimpleWarHistory()
    currentWarActual, warLogActual = ignoreSelectedWars(
        pd.Series(currentWar),
        pd.DataFrame.from_dict(warLog, orient="index"),
        ["20.2", "20.1", "20.0", "19.4", "19.3"],
    )
    currentWarExpected = pd.Series(
        {
            "a": 0,
            "b": 0,
            "c": 0,
        }
    )
    warLogExpected = pd.DataFrame.from_dict(
        {
            "a": {
                "20.1": np.nan,
                "20.0": np.nan,
                "19.4": np.nan,
            },
            "b": {
                "20.1": np.nan,
                "19.4": np.nan,
            },
            "c": {},
        },
        orient="index",
    )
    assert pd.DataFrame.equals(warLogExpected, warLogActual)
    assert pd.Series.equals(currentWarExpected, currentWarActual)
