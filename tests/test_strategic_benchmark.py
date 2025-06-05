from dataclasses import dataclass
from typing import Dict
from strategic_benchmark import strategic_benchmark
from skill_framework import ExitFromSkillException, SkillInput
from skill_framework.preview import preview_skill

from overproof_utilities import MenuColNames


class TestStrategicBenchmark:

    def _run_strategic_benchmark(self, parameters: Dict, preview: bool = False):

        skill_input: SkillInput = strategic_benchmark.create_input(arguments=parameters)
        out = strategic_benchmark(skill_input)
        if preview or self.preview:
            preview_skill(strategic_benchmark, out)

        return out

    def _assert_strategic_benchmark_runs_with_error(self, parameters: Dict, expected_exception: Exception):

        try:
            self._run_strategic_benchmark(parameters, preview=False)
        except Exception as e:
            assert isinstance(e, expected_exception)

    def _assert_strategic_benchmark_runs_without_errors(self, parameters: Dict, preview: bool = False):
        
        self._run_strategic_benchmark(parameters, preview=preview)

        assert True

@dataclass
class TestStrategicBenchmarkConfig:
    
    subject_brand_name_filter: dict
    subject_product_category_name_filter: dict
    peer_brand_name_filters: list[dict]
    peer_product_category_name_filters: list[dict]
    other_filters: list[dict]
    periods: list[str]

class TestStrategicBenchmarkGuardrails(TestStrategicBenchmark):

    config = TestStrategicBenchmarkConfig(
        subject_brand_name_filter={"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "johnnie walker"},
        subject_product_category_name_filter={"dim": MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, "op": "=", "val": "vodka"},
        peer_brand_name_filters=[
            {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "corona mexican beer"},
            {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "bacardi"}
        ],
        peer_product_category_name_filters=[
            {"dim": MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, "op": "=", "val": "gin"},
            {"dim": MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, "op": "=", "val": "rum"}
        ],
        other_filters=[],
        periods=['2024']
    )

    def test_no_subject_filter_provided(self):

        self._assert_strategic_benchmark_runs_with_error(
            parameters = {
                "periods": self.config.periods
            },
            expected_exception = ExitFromSkillException
        )

        self._assert_strategic_benchmark_runs_with_error(
            parameters = {
                "periods": self.config.periods,
                "peer_brand_name_filters": self.config.peer_brand_name_filters
            },
            expected_exception = ExitFromSkillException
        )

        self._assert_strategic_benchmark_runs_with_error(
            parameters = {
                "periods": self.config.periods,
                "peer_product_category_name_filters": self.config.peer_product_category_name_filters
            },
            expected_exception = ExitFromSkillException
        )

        self._assert_strategic_benchmark_runs_with_error(
            parameters = {
                "periods": self.config.periods,
                "peer_brand_name_filters": self.config.peer_brand_name_filters,
                "peer_product_category_name_filters": self.config.peer_product_category_name_filters
            },
            expected_exception = ExitFromSkillException
        )

class TestStrategicBenchmarkResults(TestStrategicBenchmark):

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

    def test_start(self):

        parameters = {
            "other_filters": [self.filter1],
            "periods": [self.period_filter1]
        }   

        self._assert_strategic_benchmark_runs_without_errors(parameters)