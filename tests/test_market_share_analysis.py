from typing import Dict
from market_share_analysis import market_share_analysis
from skill_framework import SkillInput
from skill_framework.preview import preview_skill


class TestMarketShareAnalysis:

    # TODO: Can this test be made generic and put into ar-analytics?

    # met1 = "sold_9le"
    met1 = "menu_placements_share"
    # met2 = "menu_placements"
    # sales_met = "sales_share" # todo: need this for overproof?
    breakout1 = "brand_name"
    breakout2 = "state_name"
    period_filter1 = "2024"
    growth_type = "Y/Y"
    filter1 = {"dim": "brand_name", "op": "=", "val": "Papa's Pilar"}
    filter2 = {"dim": "state_name", "op": "=", "val": "Florida"}

    preview = False # Set to True to get previews

    def _run_msa(self, parameters: Dict, preview: bool = False):

        skill_input: SkillInput = market_share_analysis.create_input(arguments=parameters)
        out = market_share_analysis(skill_input)
        if preview or self.preview:
            preview_skill(market_share_analysis, out)

        return out
    
    def _assert_msa_runs_without_errors(self, parameters: Dict, preview: bool = False):
        
        self._run_msa(parameters, preview=preview)

        assert True
    
    def test_single_metric_with_period(self):
        """Test with a single metric, no growth type"""

        parameters = {
            "metric": self.met1,
            "periods": [self.period_filter1],
            "other_filters": [self.filter1]
        }

        self._assert_msa_runs_without_errors(parameters)