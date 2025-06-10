"""
Tests for the BDI/CDI Opportunity skill, mirroring the strategic benchmark skill tests.
"""
from bdi_cdi_opportunity import bdi_cdi_opportunity
from skill_framework import ExitFromSkillException, SkillInput
from skill_framework.preview import preview_skill

from overproof_utilities import MenuColNames


class TestBdiCdiOpportunity:
    def _run_skill(self, parameters: dict, preview: bool = False):
        skill_input: SkillInput = bdi_cdi_opportunity.create_input(arguments=parameters)
        out = bdi_cdi_opportunity(skill_input)
        if preview or getattr(self, "preview", False):
            preview_skill(bdi_cdi_opportunity, out)
        return out

    def _assert_runs_with_error(self, parameters: dict, expected_exception):
        try:
            self._run_skill(parameters)
            assert False, f"Expected exception {expected_exception} for parameters {parameters}"
        except Exception as e:
            assert isinstance(e, expected_exception)

    def _assert_runs_without_error(self, parameters: dict):
        self._run_skill(parameters)
        assert True


class TestBdiCdiOpportunityGuardrails(TestBdiCdiOpportunity):
    def test_missing_brand(self):
        params = {
            "category_filter": ["vodka"],
            "breakout": "state_name",
            "periods": ["2024"],
            "other_filters": []
        }
        self._assert_runs_with_error(params, ExitFromSkillException)

    def test_missing_category(self):
        params = {
            "brand_filter": ["Papa's Pilar"],
            "breakout": "state_name",
            "periods": ["2024"],
            "other_filters": []
        }
        self._assert_runs_with_error(params, ExitFromSkillException)

    def test_multiple_brands(self):
        params = {
            "brand_filter": ["Papa's Pilar", "Stiegl"],
            "category_filter": ["vodka"],
            "breakout": "state_name",
            "periods": ["2024"],
            "other_filters": []
        }
        self._assert_runs_with_error(params, ExitFromSkillException)

    def test_multiple_categories(self):
        params = {
            "brand_filter": ["Papa's Pilar"],
            "category_filter": ["vodka", "gin"],
            "breakout": "state_name",
            "periods": ["2024"],
            "other_filters": []
        }
        self._assert_runs_with_error(params, ExitFromSkillException)

    def test_missing_breakout(self):
        params = {
            "brand_filter": ["Papa's Pilar"],
            "category_filter": ["vodka"],
            "periods": ["2024"],
            "other_filters": []
        }
        self._assert_runs_with_error(params, ExitFromSkillException)

    def test_invalid_breakout(self):
        params = {
            "brand_filter": ["Papa's Pilar"],
            "category_filter": ["vodka"],
            "breakout": "city",
            "periods": ["2024"],
            "other_filters": []
        }
        self._assert_runs_with_error(params, ExitFromSkillException)


class TestBdiCdiOpportunityResults(TestBdiCdiOpportunity):
    preview = False

    def test_valid_minimal(self):
        params = {
            "brand_filter": ["Papa's Pilar"],
            "category_filter": ["vodka"],
            "breakout": "state_name",
            "periods": ["2024"],
            "other_filters": []
        }
        self._assert_runs_without_error(params)

    def test_valid_with_county(self):
        params = {
            "brand_filter": ["Papa's Pilar"],
            "category_filter": ["vodka"],
            "breakout": "venue__county",
            "periods": ["2024"],
            "other_filters": []
        }
        self._assert_runs_without_error(params)

    def test_valid_with_other_filters(self):
        params = {
            "brand_filter": ["Papa's Pilar"],
            "category_filter": ["vodka"],
            "breakout": "state_name",
            "periods": ["2024"],
            "other_filters": [
                {"col": MenuColNames.COUNTRY_CODE_COL.value, "op": "=", "val": "usa"}
            ]
        }
        self._assert_runs_without_error(params)