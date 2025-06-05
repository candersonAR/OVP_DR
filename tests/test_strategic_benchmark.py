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

config = TestStrategicBenchmarkConfig(
    # subject_brand_name_filter={"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "johnnie walker"},
    subject_brand_name_filter="johnnie walker",
    # subject_product_category_name_filter={"dim": MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, "op": "=", "val": "vodka"},
    subject_product_category_name_filter="vodka",
    peer_brand_name_filters=[
        # {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "corona mexican beer"},
        "corona mexican beer",
        # {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "bacardi"}
        "bacardi"
    ],
    peer_product_category_name_filters=[
        # {"dim": MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, "op": "=", "val": "gin"},
        "gin",
        # {"dim": MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, "op": "=", "val": "rum"}
        "rum"
    ],
    other_filters=[],
    periods=['2024']
)

class TestStrategicBenchmarkGuardrails(TestStrategicBenchmark):

    config: TestStrategicBenchmarkConfig = config

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

    def test_no_period_provided(self):

        self._assert_strategic_benchmark_runs_with_error(
            parameters = {
                "subject_brand_name_filter": self.config.subject_brand_name_filter
            },
            expected_exception = ExitFromSkillException
        )

        self._assert_strategic_benchmark_runs_with_error(
            parameters = {
                "subject_product_category_name_filter": self.config.subject_product_category_name_filter
            },
            expected_exception = ExitFromSkillException
        )

class TestStrategicBenchmarkResults(TestStrategicBenchmark):

    config: TestStrategicBenchmarkConfig = config

    preview = False # Set to True to get previews

    def test_subject_brand(self):

        parameters = {
            "subject_brand_name_filter": self.config.subject_brand_name_filter,
            "periods": self.config.periods
        }   

        self._assert_strategic_benchmark_runs_without_errors(parameters)

    def test_subject_brand_with_peers(self):

        parameters = {
            "subject_brand_name_filter": self.config.subject_brand_name_filter,
            "peer_brand_name_filters": self.config.peer_brand_name_filters,
            "periods": self.config.periods
        }

        self._assert_strategic_benchmark_runs_without_errors(parameters)

    def test_subject_product_category(self):

        parameters = {
            "subject_product_category_name_filter": self.config.subject_product_category_name_filter,
            "periods": self.config.periods
        }

        self._assert_strategic_benchmark_runs_without_errors(parameters)

    def test_subject_product_category_with_peers(self): 

        parameters = {
            "subject_product_category_name_filter": self.config.subject_product_category_name_filter,
            "peer_product_category_name_filters": self.config.peer_product_category_name_filters,
            "periods": self.config.periods
        }

        self._assert_strategic_benchmark_runs_without_errors(parameters)