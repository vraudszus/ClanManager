from pathlib import Path

import jsonschema
import yaml

from player_ranking.constants import ROOT_DIR
from player_ranking.models.ranking_parameters import RankingParameters

SCHEMA_FILE: Path = ROOT_DIR / "data" / "ranking_parameters_model.yaml"


class RankingParameterValidator:
    def __init__(self, ranking_parameters):
        self.parameters = yaml.safe_load(ranking_parameters)
        self.schema = yaml.safe_load(open(SCHEMA_FILE))

    def validate(self) -> RankingParameters:
        jsonschema.validate(self.parameters, self.schema)
        parameters = RankingParameters(**self.parameters)

        # rating weights must add up to 1
        parameters.ratingWeights.check()

        return parameters
