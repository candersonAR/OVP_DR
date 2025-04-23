from ar_analytics.helpers.utils import TemplateParameterSetup, SkillPlatform, SharedFn
from overproof_data_provider import DataProvider
from overproof_utilities import MenuColNames

class TestPullData:

    metric__sales_uplift = MenuColNames.SALES_UPLIFT_METRIC.value
    metric__sold_9le = MenuColNames.SOLD_9LE_METRIC.value

    breakout__cocktail_group = MenuColNames.COCKTAIL_GROUP_COL.value
    breakout__max_time_month = MenuColNames.MAX_TIME_MONTH_COL.value
    # breakout2 = "base_size"

    filter__max_time_date__2024 = {'col': MenuColNames.MAX_TIME_DATE_COL.value, 'op': 'BETWEEN', 'val': "'2024-01-01' AND '2024-03-31'"}
    filter__brand_name__papas_pilar = {"col": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "papa's pilar"}
    filter__ingredient_of_cocktail_group__daiquiri = {"col": MenuColNames.INGREDIENT_OF_COCKTAIL_GROUP_COL.value, "op": "=", "val": "daiquiri"}

    pull_data_function = DataProvider().pull_data

    def _get_metrics(self, metrics: list[str]):
        tpms = TemplateParameterSetup(sp = SkillPlatform())
        helper = SharedFn()
        metric_props = tpms.get_metric_props()

        return [helper.get_metric_prop(metric, metric_props) for metric in metrics]

    def test_sales_uplift_by_cocktail_group_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sales_uplift]),
            breakouts = [self.breakout__cocktail_group],
            filters = [self.filter__max_time_date__2024]
        )
        assert True

    def test_sold_9le_by_cocktail_group_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sold_9le]),
            breakouts = [self.breakout__cocktail_group],
            filters = [self.filter__max_time_date__2024]
        )
        assert True
 
    def test_sales_uplift_by_cocktail_group_filtered_to_papas_pilar_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sales_uplift]) ,
            breakouts = [self.breakout__cocktail_group],
            filters = [self.filter__brand_name__papas_pilar, self.filter__max_time_date__2024]
        )
        assert True
        
    def test_sold_9le_by_cocktail_group_filtered_to_papas_pilar_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sold_9le]),
            breakouts = [self.breakout__cocktail_group],
            filters = [self.filter__brand_name__papas_pilar, self.filter__max_time_date__2024]
        )
        assert True

    def test_sales_uplift_filtered_to_papas_pilar_and_daiquiri_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sales_uplift]),
            filters = [
                self.filter__brand_name__papas_pilar, 
                self.filter__ingredient_of_cocktail_group__daiquiri, 
                self.filter__max_time_date__2024
            ]
        )
        assert True

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
        assert True