from typing import Dict
from uplift_performance import uplift_performance
from skill_framework import SkillInput
from skill_framework.preview import preview_skill
from overproof_utilities import MenuColNames

class TestUpliftPerformance:

    period__q1_2024 = "Q1 2024"

    filter__supplier_name__diageo = {"dim": MenuColNames.SUPPLIER_NAME_COL.value, "op": "=", "val": ["diageo usa"]}
    filter__supplier_name__bacardi = {"dim": MenuColNames.SUPPLIER_NAME_COL.value, "op": "=", "val": ["bacardi"]}
    filter__brand_name__heineken = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["heineken brewing"]}
    filter__brand_name__papa_pilar = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["Papa's Pilar"]}
    filter__brand_name__mijenta = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["mijenta tequila"]}
    filter__brand_name__don_papa = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["don papa"]}
    filter__brand_name__parini = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["parini"]}

    preview = False

    def _run_uplift_performance(self, parameters: Dict, preview: bool = False):

        skill_input: SkillInput = uplift_performance.create_input(arguments=parameters)
        out = uplift_performance(skill_input)
        if preview or self.preview:
            preview_skill(uplift_performance, out)

        return out
    
    def _assert_uplift_performance_runs_without_errors(self, parameters: Dict, preview: bool = False):
        
        self._run_uplift_performance(parameters, preview=preview)

        assert True

    def test_uplift_performance_with_supplier_name(self):
        
        self._assert_uplift_performance_runs_without_errors(parameters={
            'periods': [],
            'other_filters': [self.filter__supplier_name__diageo]
        })

    def test_uplift_performance_with_brand_name(self):
        
        self._assert_uplift_performance_runs_without_errors(parameters={
            'periods': ['2024'],
            'other_filters': [self.filter__brand_name__papa_pilar]
        })
    
    # def test_uplift_performance_with_brand_name_and_supplier_name(self):
        
    #     self._assert_uplift_performance_runs_without_errors(parameters={
    #         'periods': ['2022'],
    #         'other_filters': [self.filter__brand_name__don_papa, self.filter__supplier_name__diageo]
    #     })