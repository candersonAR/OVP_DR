from typing import Dict
from trend import trend
from skill_framework import SkillInput
from skill_framework.preview import preview_skill


class TestTrend:

    # TODO: Can this test be made generic and put into ar-analytics?

    met1 = "sold_9le"
    met2 = "menu_placements"
    # sales_met = "sales_share" # todo: need this for overproof?
    breakout1 = "brand_name"
    breakout2 = "state_name"
    period_filter1 = "2024"
    growth_type = "Y/Y"
    filter1 = {"dim": "brand_name", "op": "=", "val": "Papa's Pilar"}
    filter2 = {"dim": "state_name", "op": "=", "val": "Florida"}

    preview = False # Set to True to get previews

    def _assert_trend_runs_without_errors(self, parameters: Dict, preview: bool = False):

        skill_input: SkillInput = trend.create_input(arguments=parameters)
        out = trend(skill_input)
        if preview or self.preview:
            preview_skill(trend, out)

        assert True

    # def test_full_trend_skill(self):
    #     '''
    #     Checks to see if the full trend skill runs without errors
    #     '''

    #     # currently assumes it's attached to the pasta dataset

    #     skill_input: SkillInput = trend.create_input(arguments={'metrics': ["sold_9le", "menu_placements"], 'other_filters': [{"dim": "brand_name", "op": "=", "val": ["Papa's Pilar"]}]})
    #     out = trend(skill_input)
    #     preview_skill(trend, out)

    #     assert True

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
            "growth_type": self.growth_type
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
            "growth_type": self.growth_type
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
            "growth_type": self.growth_type
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
            "growth_type": self.growth_type
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
            "growth_type": self.growth_type
        }

        self._assert_trend_runs_without_errors(parameters)
