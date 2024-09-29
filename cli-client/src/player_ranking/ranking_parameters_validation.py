import math
from pathlib import Path

import jsonschema
import yaml

from player_ranking.constants import ROOT_DIR
from player_ranking.ranking_parameters import RankingParameters

SCHEMA_FILE: Path = ROOT_DIR / "data" / "ranking_parameters_model.yaml"


class RankingParameterValidator:
    def __init__(self, ranking_parameters: str):
        self.parameters = yaml.safe_load(ranking_parameters)
        self.schema = yaml.safe_load(open(SCHEMA_FILE))

    def validate(self) -> RankingParameters:
        jsonschema.validate(self.parameters, self.schema)
        parameters = RankingParameters(**self.parameters)

        # rating weights must add up to 1
        if not math.isclose(sum(parameters.ratingWeights.sum_of_weights()), 1):
            raise ValueError("Sum of ratingWeights must be 1.")

        return parameters
