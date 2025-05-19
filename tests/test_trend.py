from typing import Dict
from overproof_trend import trend
from skill_framework import SkillInput
from skill_framework.preview import preview_skill

from overproof_utilities import MenuColNames


class TestTrend:

    # TODO: Can this test be made generic and put into ar-analytics?

    met1 = MenuColNames.SOLD_9LE_METRIC.value
    met2 = MenuColNames.MENU_PLACEMENTS_METRIC.value
    metric__menu_placements_share = MenuColNames.MENU_PLACEMENTS_SHARE_METRIC.value
    sales_uplift = MenuColNames.SALES_UPLIFT_METRIC.value
    sold_cases = MenuColNames.SOLD_CASES_METRIC.value

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

    def _assert_trend_runs_without_errors(self, parameters: Dict, preview: bool = False):

        skill_input: SkillInput = trend.create_input(arguments=parameters)
        out = trend(skill_input)
        if preview or self.preview:
            preview_skill(trend, out)

        assert True

    def test_single_metric(self):
        """Test with a single metric, no growth type, no breakout"""

        parameters = {
            "metrics": [self.met1]
        }   

        self._assert_trend_runs_without_errors(parameters)

    def test_single_metric_with_period(self):
        """Test with a single metric, no growth type"""

        parameters = {
            "metrics": [self.met1],
            "periods": [self.period_filter1]
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_single_metric_with_period_and_growth_type(self):
        """Test with a single metric, growth type"""

        parameters = {
            "metrics": [self.met1],
            "periods": [self.period_filter1],
            "growth_type": self.growth_type__yoy
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_single_metric_with_period_and_breakout(self):
        """Test with a single metric, breakout"""

        parameters = {
            "metrics": [self.met1],
            "periods": [self.period_filter1],
            "breakouts": [self.breakout1]
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_single_metric_with_period_and_filter(self):
        """Test with a single metric, period, and filter"""

        parameters = {
            "metrics": [self.met1],
            "periods": [self.period_filter1],
            "other_filters": [self.filter1]
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_single_metric_with_period_and_breakout_and_filter(self):
        """Test with a single metric, period, breakout, and filter"""

        parameters = {
            "metrics": [self.met1],
            "periods": [self.period_filter1],
            "breakouts": [self.breakout1],
            "other_filters": [self.filter1]
        }

        self._assert_trend_runs_without_errors(parameters)  
        
    def test_single_metric_with_period_and_breakout_and_filter_and_filter2(self):
        """Test with a single metric, period, breakout, filter, and filter2"""

        parameters = {
            "metrics": [self.met1],
            "periods": [self.period_filter1],
            "breakouts": [self.breakout1],
            "other_filters": [self.filter1, self.filter2]
        }

        self._assert_trend_runs_without_errors(parameters)
        
    def test_single_metric_with_period_and_breakout_and_filter_and_filter2_and_growth_type(self):
        """Test with a single metric, period, breakout, filter, filter2, and growth type"""

        parameters = {
            "metrics": [self.met1],
            "periods": [self.period_filter1],
            "breakouts": [self.breakout1],
            "other_filters": [self.filter1, self.filter2],
            "growth_type": self.growth_type__yoy
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_multiple_metrics(self):
        """Test with multiple metrics, no growth type, no breakout"""

        parameters = {
            "metrics": [self.met1, self.met2]
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_multiple_metrics_with_period(self):
        """Test with multiple metrics, period, no growth type, no breakout"""

        parameters = {
            "metrics": [self.met1, self.met2],
            "periods": [self.period_filter1]
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_multiple_metrics_with_period_and_growth_type(self):
        """Test with multiple metrics, period, growth type, no breakout"""

        parameters = {
            "metrics": [self.met1, self.met2],
            "periods": [self.period_filter1],
            "growth_type": self.growth_type__yoy
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_multiple_metrics_with_period_and_breakout(self):
        """Test with multiple metrics, period, breakout"""

        parameters = {
            "metrics": [self.met1, self.met2],
            "periods": [self.period_filter1],
            "breakouts": [self.breakout1]
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_multiple_metrics_with_period_and_breakout_and_growth_type(self):
        """Test with multiple metrics, period, breakout, and growth type"""

        parameters = {
            "metrics": [self.met1, self.met2],
            "periods": [self.period_filter1],
            "breakouts": [self.breakout1],
            "growth_type": self.growth_type__yoy
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_multiple_metrics_with_period_and_breakout_and_filter(self):
        """Test with multiple metrics, period, breakout, and filter"""

        parameters = {
            "metrics": [self.met1, self.met2],
            "periods": [self.period_filter1],
            "breakouts": [self.breakout1],
            "other_filters": [self.filter1]
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_multiple_metrics_with_period_and_breakout_and_filter_and_filter2(self):
        """Test with multiple metrics, period, breakout, filter, and filter2"""

        parameters = {
            "metrics": [self.met1, self.met2],
            "periods": [self.period_filter1],
            "breakouts": [self.breakout1],
            "other_filters": [self.filter1, self.filter2]
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_multiple_metrics_with_period_and_breakout_and_filter_and_filter2_and_growth_type(self):
        """Test with multiple metrics, period, breakout, filter, filter2, and growth type"""

        parameters = {
            "metrics": [self.met1, self.met2],
            "periods": [self.period_filter1],
            "breakouts": [self.breakout1],
            "other_filters": [self.filter1, self.filter2],
            "growth_type": self.growth_type__yoy
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_sales_uplift_by_cocktail_group_in_2024(self):
        """Test sales uplift by cocktail group in 2024"""

        parameters = {
            "metrics": [self.sales_uplift],
            "periods": [self.period_filter1],
            "breakouts": [self.breakout2]
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_sales_uplift_and_sold_9le_by_brand_in_q1_2024(self):
        """
        Test sales uplift and sold 9le by brand in q1 2024

        From CON-3859
        """

        parameters = {
            "metrics": [self.sales_uplift, self.met1],
            "periods": [self.period_filter1],
            "other_filters": [
                {
                    "val": [
                        "papa's pilar"
                    ],
                    "dim": "brand_name",
                    "op": "="
                },
                {
                    "val": [
                        "miami"
                    ],
                    "dim": "venue__city",
                    "op": "="
                }
            ]
        }
        
        self._assert_trend_runs_without_errors(parameters)

    def test_sales_uplift_and_sold_cases_in_q1_2024_filtered_to_papas_pilar_and_miami(self):

        parameters = {
            "metrics": [
                self.sales_uplift,
                self.sold_cases
            ],
            "periods": [
                "q1 2024"
            ],
            "other_filters": [
                {
                    "val": [
                        "papa's pilar"
                    ],
                    "dim": "brand_name",
                    "op": "="
                },
                {
                    "val": [
                        "miami"
                    ],
                    "dim": "venue__city",
                    "op": "="
                }
            ]
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_sales_uplift_and_sold_cases_by_brand_name_in_2024_yoy_growth(self):

        parameters = {
            "metrics": [
                self.sales_uplift,
                self.sold_cases
            ],
            "time_granularity": "month",
            "periods": [
                self.period_filter1
            ],
            "breakouts": [
                self.breakout1
            ],
            # "growth_type": self.growth_type__yoy
            "growth_type": self.growth_type__pop
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_menu_placements_share_by_brand_in_q1_2024(self):

        parameters = {
            'metrics': [self.metric__menu_placements_share, self.met2],
            'breakouts': [self.breakout1],
            'periods': [self.period_filter1],
            "time_granularity": "month"
        }

        self._assert_trend_runs_without_errors(parameters)

    def test_menu_placements_share_by_category_in_q1_2024(self):

        parameters = {
            'metrics': [self.metric__menu_placements_share, self.met2],
            'breakouts': [self.breakout3],
            'periods': [self.period_filter1],
            "time_granularity": "month"
        }

        self._assert_trend_runs_without_errors(parameters)
