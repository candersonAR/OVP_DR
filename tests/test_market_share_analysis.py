from typing import Dict
from market_share_analysis import market_share_analysis
from skill_framework import SkillInput
from skill_framework.preview import preview_skill


class TestMarketShareAnalysis:

    # TODO: Can this test be made generic and put into ar-analytics?

    # met1 = "sold_9le"
    metric_menu_placement_share = "menu_placements_share"
    # met2 = "menu_placements"
    # sales_met = "sales_share" # todo: need this for overproof?
    breakout1 = "brand_name"
    breakout2 = "state_name"
    period_filter_2024 = "2024"
    growth_type = "Y/Y"
    papa_pillars_filter = {"dim": "brand_name", "op": "=", "val": "Papa's Pilar"}
    margarita_filter = {"val":["margarita"],"dim":"cocktail__name","op":"="}
    vodka_filter = {"dim": "product_category_name", "op": "=", "val": "vodka"}

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
    
    def test_menu_placement_share_in_2024_for_papa_pillars(self):
        """Test with a single metric, no growth type"""

        parameters = {
            "metric": self.metric_menu_placement_share,
            "periods": [self.period_filter_2024],
            "other_filters": [self.papa_pillars_filter]
        }

        self._assert_msa_runs_without_errors(parameters)

    def test_menu_placement_share_in_2024_for_margarita(self):
        """Test with a single metric, no growth type"""

        parameters = {
            "metric": self.metric_menu_placement_share,
            "periods": [self.period_filter_2024],
            "other_filters": [self.margarita_filter]
        }

        self._assert_msa_runs_without_errors(parameters)

    def test_menu_placement_share_in_2024_for_vodka(self):
        """Test with a single metric, no growth type"""

        parameters = {
            "metric": self.metric_menu_placement_share,
            "periods": [self.period_filter_2024],
            "other_filters": [self.vodka_filter]
        }

        self._assert_msa_runs_without_errors(parameters)

    def test_menu_placement_share_in_2024_for_triple_sec_and_cointreau(self):
        """Test with a single metric, no growth type"""

        self._assert_msa_runs_without_errors(
            parameters = {
                "metric": self.metric_menu_placement_share,
                "periods": [self.period_filter_2024],
                "other_filters": [
                    {
                        "val": [
                            "cointreau"
                        ],
                        "dim": "brand_name",
                        "op": "="
                    },
                    {
                        "val": [
                            "triple sec"
                        ],
                        "dim": "product_category_name",
                        "op": "="
                    }
                ]
            }
        )

    def test_menu_placement_share_in_2024_for_new_york_and_cointreau(self):
        """Test with a single metric, no growth type"""

        self._assert_msa_runs_without_errors(
            parameters = {
                "metric": self.metric_menu_placement_share,
                "periods": [self.period_filter_2024],
                "other_filters": [
                    {
                        "val": [
                            "cointreau"
                        ],
                        "dim": "brand_name",
                        "op": "="
                    },
                    {
                        "val": [
                            "new york"
                        ],
                        "dim": "state_name",
                        "op": "="
                    }
                ]
            }
        )

    def test_margarita_failing_period_case(self):

        parameters = {
            "growth_type": "Y/Y",
            "periods": [
                "jan 2025"
            ],
            "other_filters": [
                {
                "val": [
                    "margarita"
                ],
                "dim": "cocktail__name",
                "op": "="
                }
            ]
        }

        self._assert_msa_runs_without_errors(parameters)
