from typing import List

from decorator import decorator

from player_ranking.models.ranking_parameters import RankingParameters


@decorator
def set_ignore_wars(func, ranking_parameters: RankingParameters, wars: List[str], *args, **kw):
    ranking_parameters.ignoreWars = wars
    result = func(ranking_parameters, *args, **kw)
    return result
