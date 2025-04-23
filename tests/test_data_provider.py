from ar_analytics.helpers.utils import TemplateParameterSetup, SkillPlatform, SharedFn
from overproof_data_provider import DataProvider
from overproof_utilities import MenuColNames

class TestPullData:

    metric__sales_uplift = MenuColNames.SALES_UPLIFT_METRIC.value
    metric__sold_9le = MenuColNames.SOLD_9LE_METRIC.value
    metric__sold_cases = MenuColNames.SOLD_CASES_METRIC.value
    
    breakout__cocktail_group = MenuColNames.COCKTAIL_GROUP_COL.value
    breakout__max_time_month = MenuColNames.MAX_TIME_MONTH_COL.value
    breakout__brand_name = MenuColNames.BRAND_NAME_COL.value

    filter__max_time_date__2024 = {'col': MenuColNames.MAX_TIME_DATE_COL.value, 'op': 'BETWEEN', 'val': "'2024-01-01' AND '2024-03-31'"}
    filter__brand_name__papas_pilar = {"col": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "papa's pilar"}
    filter__ingredient_of_cocktail_group__daiquiri = {"col": MenuColNames.INGREDIENT_OF_COCKTAIL_GROUP_COL.value, "op": "=", "val": "daiquiri"}

    pull_data_function = DataProvider().pull_data

    def _get_metrics(self, metrics: list[str]):
        tpms = TemplateParameterSetup(sp = SkillPlatform())
        helper = SharedFn()
        metric_props = tpms.get_metric_props()

        return [helper.get_metric_prop(metric, metric_props) for metric in metrics]
    
    def assert_value_between(self, value, min_value, max_value):
        assert min_value <= value <= max_value, f"{value} is not between {min_value} and {max_value}"
    
    def assert_value_between_threshold(self, value, expected_value, threshold):
        self.assert_value_between(value, expected_value - threshold, expected_value + threshold)

    def test_sales_uplift_by_cocktail_group_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sales_uplift]),
            breakouts = [self.breakout__cocktail_group],
            filters = [self.filter__max_time_date__2024]
        )
        assert self.metric__sales_uplift in df.columns
        assert self.breakout__cocktail_group in df.columns

    def test_sold_9le_by_cocktail_group_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sold_9le]),
            breakouts = [self.breakout__cocktail_group],
            filters = [self.filter__max_time_date__2024]
        )
        assert self.metric__sold_9le in df.columns
        assert self.breakout__cocktail_group in df.columns
 
    def test_sales_uplift_by_cocktail_group_filtered_to_papas_pilar_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sales_uplift]) ,
            breakouts = [self.breakout__cocktail_group],
            filters = [self.filter__brand_name__papas_pilar, self.filter__max_time_date__2024]
        )
        assert self.metric__sales_uplift in df.columns
        assert self.breakout__cocktail_group in df.columns
        
    def test_sold_9le_by_cocktail_group_filtered_to_papas_pilar_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sold_9le]),
            breakouts = [self.breakout__cocktail_group],
            filters = [self.filter__brand_name__papas_pilar, self.filter__max_time_date__2024]
        )
        assert self.metric__sold_9le in df.columns
        assert self.breakout__cocktail_group in df.columns

    def test_sales_uplift_filtered_to_papas_pilar_and_daiquiri_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sales_uplift]),
            filters = [
                self.filter__brand_name__papas_pilar, 
                self.filter__ingredient_of_cocktail_group__daiquiri, 
                self.filter__max_time_date__2024
            ]
        )
        assert self.metric__sales_uplift in df.columns
        assert len(df) == 1

        # TODO: Validate this value
        uplift_value = df[self.metric__sales_uplift].values[0]
        self.assert_value_between_threshold(uplift_value, 0.26769106669107506, 0.001)

    def test_sales_uplift_by_month_in_2024_filtered_to_papas_pilar_and_daiquiri(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sales_uplift]),
            breakouts = [self.breakout__max_time_month],
            filters = [
                self.filter__brand_name__papas_pilar, 
                self.filter__ingredient_of_cocktail_group__daiquiri, 
                self.filter__max_time_date__2024
            ]
        )
        assert self.metric__sales_uplift in df.columns
        assert self.breakout__max_time_month in df.columns

    def test_sales_uplift_and_sold_cases_in_q1_2024(self):

        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sales_uplift, self.metric__sold_cases]),
            filters = [self.filter__brand_name__papas_pilar, self.filter__max_time_date__2024]
        )
        assert self.metric__sales_uplift in df.columns
        assert self.metric__sold_cases in df.columns

    def test_sales_uplift_by_brand_filtered_to_daiquiri_in_q1_2024(self):
        """
        Testing a non-cross breakout.
        """

        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sales_uplift]),
            breakouts = [self.breakout__brand_name],
            filters = [
                self.filter__ingredient_of_cocktail_group__daiquiri, 
                self.filter__max_time_date__2024
            ]
        )
        assert self.breakout__brand_name in df.columns
        assert self.metric__sales_uplift in df.columns