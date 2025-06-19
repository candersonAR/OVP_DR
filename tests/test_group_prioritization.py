from typing import Dict
from group_prioritization import group_prioritization
from skill_framework import SkillInput, ExitFromSkillException
from skill_framework.preview import preview_skill
from overproof_utilities import MenuColNames

class TestGroupPrioritization:

    period__2024 = "2024"
    period__ytd = "ytd"

    filter__supplier_name__diageo = {"dim": MenuColNames.SUPPLIER_NAME_COL.value, "op": "=", "val": ["diageo usa"]}
    filter__supplier_name__bacardi = {"dim": MenuColNames.SUPPLIER_NAME_COL.value, "op": "=", "val": ["bacardi"]}
    filter__brand_name__heineken = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["heineken brewing"]}
    filter__brand_name__bacardi = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["bacardi"]}
    filter__brand_name__captain_morgan = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["captain morgan"]}
    filter__brand_name__papa_pilar = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["Papa's Pilar"]}
    filter__brand_name__mijenta = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["mijenta tequila"]}
    filter__brand_name__don_papa = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["don papa"]}
    filter__brand_name__parini = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["parini"]}

    preview = False

    def _run_group_prioritization(self, parameters: Dict, preview: bool = False):

        skill_input: SkillInput = group_prioritization.create_input(arguments=parameters)
        out = group_prioritization(skill_input)
        if preview or self.preview:
            preview_skill(group_prioritization, out)

        return out
    
    def _assert_group_prioritization_runs_without_errors(self, parameters: Dict, preview: bool = False):
        
        self._run_group_prioritization(parameters, preview=preview)

        assert True
    

    def test_group_prioritization(self):
        
        self._assert_group_prioritization_runs_without_errors(parameters={
            'periods': [self.period__ytd],
            "benchmark_brand": "papa's pilar",
            'other_filters': [self.filter__brand_name__mijenta]
        })

    def test_group_prioritization_bacardi_vs_captain_morgan(self):
        
        self._assert_group_prioritization_runs_without_errors(parameters={
            'periods': [self.period__ytd],
            "benchmark_brand": "captain morgan",
            'other_filters': [self.filter__brand_name__bacardi]
        })

    def test_group_prioritization_limit_n(self):
        
        self._assert_group_prioritization_runs_without_errors(parameters={
            'periods': [self.period__ytd],
            "benchmark_brand": "captain morgan",
            'other_filters': [self.filter__brand_name__bacardi],
            'limit_n': 5
        })

    def test_no_period_provided(self):
        
        self._assert_group_prioritization_runs_without_errors(parameters={
            'periods': [self.period__2024],
            "benchmark_brand": "papa's pilar",
            'other_filters': [self.filter__brand_name__mijenta]
        })
    
    def test_group_prioritization_multiple_brands(self):
        try:
            self._assert_group_prioritization_runs_without_errors(parameters={
                'periods': [self.period__ytd],
                "benchmark_brand": "papa's pilar",
                'other_filters': [self.filter__brand_name__mijenta, self.filter__brand_name__papa_pilar]
            })
            self.fail("Expected ExitFromSkillException was not raised")
        except ExitFromSkillException as e:
            assert "Multiple brand filters found" in str(e)
    

    def test_title_and_subtitle(self):
        
        out = self._run_group_prioritization(parameters={
            'periods': [self.period__ytd],
            "benchmark_brand": "ten to one rum",
            'other_filters': [self.filter__brand_name__papa_pilar]
        })

        # assert out.title == "Group Prioritization"
        # assert out.subtitle == "Group Prioritization"