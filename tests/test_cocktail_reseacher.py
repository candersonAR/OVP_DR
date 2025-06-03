from ar_analytics.helpers.utils import TemplateParameterSetup, SkillPlatform, SharedFn
from overproof_data_provider import DataProvider
from overproof_utilities import MenuColNames
import pytest

class TestPullData:
    # TODO: Add support for single spirit uplift and cocktail uplift, rewrite all tests using metric__sales_uplift
    metric__menu_uplift = MenuColNames.MENU_UPLIFT_METRIC.value
    metric__single_spirit_uplift = MenuColNames.SINGLE_SPIRIT_UPLIFT_METRIC.value
    metric__cocktail_uplift = MenuColNames.COCKTAIL_UPLIFT_METRIC.value
    metric__sold_9le = MenuColNames.SOLD_9LE_METRIC.value
    metric__sold_cases = MenuColNames.SOLD_CASES_METRIC.value
    
    breakout__cocktail_group = MenuColNames.COCKTAIL_GROUP_COL.value
    breakout__max_time_month = MenuColNames.MAX_TIME_MONTH_COL.value
    breakout__brand_name = MenuColNames.BRAND_NAME_COL.value
    breakout__product_category_name = MenuColNames.PRODUCT_CATEGORY_NAME_COL.value


    filter__max_time_date__Q1_2024 = {'col': MenuColNames.MAX_TIME_DATE_COL.value, 'op': 'BETWEEN', 'val': "'2024-01-01' AND '2024-03-31'"}
    filter__max_time_date__2024 = {'col': MenuColNames.MAX_TIME_DATE_COL.value, 'op': 'BETWEEN', 'val': "'2024-01-01' AND '2024-12-31'"}
    filter__max_time_date__jan_2025 = {'col': MenuColNames.MAX_TIME_DATE_COL.value, 'op': 'BETWEEN', 'val': "'2025-01-01' AND '2025-01-31'"}
    filter__max_time_date__feb_2023_to_feb_2025 = {'col': MenuColNames.MAX_TIME_DATE_COL.value, 'op': 'BETWEEN', 'val': "'2023-02-01' AND '2025-02-28'"}
    filter__brand_name__papas_pilar = {"col": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "papa's pilar"}
    filter__brand_name__stiegl = {"col": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "stiegl"}
    filter__brand_name__erdinger = {"col": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": "erdinger"}
    filter__product_category_name__american_rye_malt_whiskey = {"col": MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, "op": "=", "val": "american rye malt whiskey"}
    filter__ingredient_of_cocktail_name = {"col": MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value, "op": "in", "val": ["daiquiri", "mojito"]}
    filter__ingredient_of_cocktail_name__daiquiri = {"col": MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value, "op": "=", "val": "daiquiri"}
    filter__ingredient_of_cocktail_name__mojito = {"col": MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value, "op": "=", "val": "mojito"}
    filter__country__canada = {"col": MenuColNames.COUNTRY_CODE_COL.value, "op": "=", "val": "can"}
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

    def test_menu_uplift_by_cocktail_group_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__menu_uplift]),
            breakouts = [self.breakout__cocktail_group],
            filters = [self.filter__max_time_date__Q1_2024, self.filter__brand_name__papas_pilar]
        )
        assert self.metric__menu_uplift in df.columns
        assert self.breakout__cocktail_group in df.columns
    
    
