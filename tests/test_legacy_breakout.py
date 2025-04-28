from typing import Dict
from dimension_breakout import simple_breakout
from skill_framework import SkillInput
from skill_framework.preview import preview_skill
from overproof_utilities import MenuColNames

class TestLegacyBreakout:

    metric__sold_9le = MenuColNames.SOLD_9LE_METRIC.value
    metric__menu_placements = MenuColNames.MENU_PLACEMENTS_METRIC.value
    metric__sales_uplift = MenuColNames.SALES_UPLIFT_METRIC.value

    breakout__cocktail_family = MenuColNames.COCKTAIL_FAMILY_COL.value
    breakout__brand_name = MenuColNames.BRAND_NAME_COL.value
    breakout__cocktail_group = MenuColNames.COCKTAIL_GROUP_COL.value

    period__q1_2024 = "Q1 2024"

    filter__brand_name__papa_pilar = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["Papa's Pilar"]}
    filter__cocktail_group__margaritas = {"dim": MenuColNames.COCKTAIL_GROUP_COL.value, "op": "=", "val": ["margaritas"]}
    filter__brand_name__parini = {"dim": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": ["parini"]}

    preview = False

    def _run_simple_breakout(self, parameters: Dict, preview: bool = False):

        skill_input: SkillInput = simple_breakout.create_input(arguments=parameters)
        out = simple_breakout(skill_input)
        if preview or self.preview:
            preview_skill(simple_breakout, out)

        return out
    
    def _assert_simple_breakout_runs_without_errors(self, parameters: Dict, preview: bool = False):
        
        self._run_simple_breakout(parameters, preview=preview)

        assert True

    def test_menu_placements_by_cocktail_family_for_papa_pilar_in_q1_2024(self):
        
        self._assert_simple_breakout_runs_without_errors(parameters={
            'metrics': [self.metric__menu_placements], 
            'breakouts': [self.breakout__cocktail_family], 
            'periods': [self.period__q1_2024],
            'other_filters': [self.filter__brand_name__papa_pilar]
        })

    def test_menu_placements_by_brand_name_for_margarita_in_q1_2024(self):

        self._assert_simple_breakout_runs_without_errors(parameters={
            'metrics': [self.metric__menu_placements], 
            'breakouts': [self.breakout__brand_name], 
            'periods': [self.period__q1_2024],
            'other_filters': [self.filter__cocktail_group__margaritas]
        })

    def test_sales_uplift_by_cocktail_group_for_papa_pilar_in_q1_2024(self):

        self._assert_simple_breakout_runs_without_errors(parameters={
            'metrics': [self.metric__sales_uplift],
            'breakouts': [self.breakout__cocktail_group],
            'periods': [self.period__q1_2024],
            'other_filters': [self.filter__brand_name__papa_pilar]
        })

    def test_sales_uplift_by_brand_in_q1_2024(self):

        self._assert_simple_breakout_runs_without_errors(parameters={
            'metrics': [self.metric__sales_uplift],
            'breakouts': [self.breakout__brand_name],
            'periods': [self.period__q1_2024]
        })
