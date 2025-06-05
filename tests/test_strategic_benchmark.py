from typing import Dict
from strategic_benchmark import strategic_benchmark
from skill_framework import SkillInput
from skill_framework.preview import preview_skill

from overproof_utilities import MenuColNames

class TestStrategicBenchmark:

    # sales_met = "sales_share" # todo: need this for overproof?
    breakout1 = MenuColNames.BRAND_NAME_COL.value
    breakout2 = MenuColNames.COCKTAIL_GROUP_COL.value
    breakout3 = MenuColNames.PRODUCT_CATEGORY_NAME_COL.value
    period_filter1 = "2024"
    growth_type__yoy = "Y/Y"
    growth_type__pop = "P/P"
    filter1 = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "Papa's Pilar"}
    filter2 = {"dim": MenuColNames.COCKTAIL_GROUP_COL.value, "op": "=", "val": "Margaritas"}


    preview = False # Set to True to get previews

    def _assert_strategic_benchmark_runs_without_errors(self, parameters: Dict, preview: bool = False):

        skill_input: SkillInput = strategic_benchmark.create_input(arguments=parameters)
        out = strategic_benchmark(skill_input)
        if preview or self.preview:
            preview_skill(strategic_benchmark, out)

        assert True

    def test_start(self):

        parameters = {
            "other_filters": [self.filter1],
            "periods": [self.period_filter1]
        }   

        self._assert_strategic_benchmark_runs_without_errors(parameters)