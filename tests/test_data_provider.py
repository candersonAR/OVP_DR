from ar_analytics.helpers.utils import TemplateParameterSetup, SkillPlatform, SharedFn
from overproof_data_provider import DataProvider
from overproof_utilities import MenuColNames
import pytest

class TestPullData:
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
            breakouts = [],
            filters = [self.filter__max_time_date__Q1_2024, self.filter__brand_name__papas_pilar]
        )
        assert self.metric__menu_uplift in df.columns

        uplift_value = df[self.metric__menu_uplift].values[0]
        self.assert_value_between_threshold(uplift_value, 2.381, 0.001)
    
    def test_single_spirit_uplift_by_cocktail_group_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__single_spirit_uplift]),
            breakouts = [],
            filters = [self.filter__max_time_date__Q1_2024, self.filter__brand_name__papas_pilar]
        )
        assert self.metric__single_spirit_uplift in df.columns

        uplift_value = df[self.metric__single_spirit_uplift].values[0]
        self.assert_value_between_threshold(uplift_value, 1.0785, 0.001)
    
    def test_general_cocktail_uplift_by_cocktail_group_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__cocktail_uplift]),
            breakouts = [],
            filters = [self.filter__max_time_date__Q1_2024, self.filter__brand_name__papas_pilar]
        )
        assert self.metric__cocktail_uplift in df.columns

        uplift_value = df[self.metric__cocktail_uplift].values[0]
        self.assert_value_between_threshold(uplift_value, 3.312, 0.001)
    
    def test_single_specific_cocktail_uplift_by_cocktail_group_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__cocktail_uplift]),
            breakouts = [],
            filters = [self.filter__max_time_date__Q1_2024, self.filter__brand_name__papas_pilar, self.filter__ingredient_of_cocktail_name__daiquiri]
        )
        assert self.metric__cocktail_uplift in df.columns

        uplift_value = df[self.metric__cocktail_uplift].values[0]
        self.assert_value_between_threshold(uplift_value, 3.509, 0.001)

    def test_multiple_specific_cocktail_uplift_by_cocktail_group_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__cocktail_uplift]),
            breakouts = [],
            filters = [self.filter__max_time_date__Q1_2024, self.filter__brand_name__papas_pilar, self.filter__ingredient_of_cocktail_name]
        )
        assert self.metric__cocktail_uplift in df.columns


    def test_uplift_single_metric_guardrail(self):
        # Test that only one sales uplift metric is allowed
        metrics = [
            {"name": MenuColNames.COCKTAIL_UPLIFT_METRIC.value},
            {"name": MenuColNames.MENU_UPLIFT_METRIC.value}
        ]
        filters = [{"col": MenuColNames.BRAND_NAME_COL.value, "op": "equals", "val": "Test Brand"}]
        
        with pytest.raises(Exception) as exc_info:
            self.pull_data_function(metrics=metrics, filters=filters)
        assert "Only one sales uplift metric is supported at a time" in str(exc_info.value)

    def test_uplift_brand_or_supplier_guardrail(self):
        # Test that either brand or supplier filter is required
        metrics = [{"name": MenuColNames.COCKTAIL_UPLIFT_METRIC.value}]
        filters = [{"col": MenuColNames.VENUE_PREMISE_TYPE_COL.value, "op": "equals", "val": "On-Premise"}]
        
        with pytest.raises(Exception) as exc_info:
            self.pull_data_function(metrics=metrics, filters=filters)
        assert "Either brand_name or supplier_name is required to calculate sales uplift" in str(exc_info.value)

    def test_uplift_cocktail_filter_guardrail(self):
        # Test that cocktail filters are only allowed with cocktail uplift
        metrics = [{"name": MenuColNames.SINGLE_SPIRIT_UPLIFT_METRIC.value}]
        filters = [
            {"col": MenuColNames.BRAND_NAME_COL.value, "op": "equals", "val": "Test Brand"},
            {"col": MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value, "op": "equals", "val": "Test Cocktail"}
        ]
        
        with pytest.raises(Exception) as exc_info:
            self.pull_data_function(metrics=metrics, filters=filters)
        assert "is not supported with cocktail filter dimensions" in str(exc_info.value)

    def test_uplift_premise_filter_guardrail(self):
        # Test that on-premise filter is not allowed
        metrics = [{"name": MenuColNames.MENU_UPLIFT_METRIC.value}]
        filters = [
            self.filter__brand_name__papas_pilar,
            {"col": MenuColNames.VENUE_PREMISE_TYPE_COL.value, "op": "equals", "val": "On-Premise"}
        ]
        
        with pytest.raises(Exception) as exc_info:
            self.pull_data_function(metrics=metrics, filters=filters)
        assert "Sales uplift is not supported filtering on venue__premise_type" in str(exc_info.value)

    def test_sold_9le_by_cocktail_group_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sold_9le]),
            breakouts = [self.breakout__cocktail_group],
            filters = [self.filter__max_time_date__Q1_2024]
        )
        assert self.metric__sold_9le in df.columns
        assert self.breakout__cocktail_group in df.columns
 
        
    def test_sold_9le_by_cocktail_group_filtered_to_papas_pilar_in_2024(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__sold_9le]),
            breakouts = [self.breakout__cocktail_group],
            filters = [self.filter__brand_name__papas_pilar, self.filter__max_time_date__Q1_2024]
        )
        assert self.metric__sold_9le in df.columns
        assert self.breakout__cocktail_group in df.columns

    # def test_sales_uplift_filtered_to_papas_pilar_and_daiquiri_in_2024(self):
    #     df = self.pull_data_function(
    #         metrics = self._get_metrics([self.metric__cocktail_uplift]),
    #         filters = [
    #             self.filter__brand_name__papas_pilar, 
    #             self.filter__ingredient_of_cocktail_name__daiquiri, 
    #             self.filter__max_time_date__Q1_2024
    #         ]
    #     )
    #     assert self.metric__cocktail_uplift in df.columns
    #     assert len(df) == 1

    #     # TODO: Validate this value
    #     uplift_value = df[self.metric__cocktail_uplift].values[0]
    #     self.assert_value_between_threshold(uplift_value, 0.26769106669107506, 0.001)

    def test_sales_uplift_by_month_in_2024_filtered_to_papas_pilar_and_daiquiri(self):
        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__cocktail_uplift]),
            breakouts = [self.breakout__max_time_month],
            filters = [
                self.filter__brand_name__papas_pilar, 
                self.filter__ingredient_of_cocktail_name__daiquiri, 
                self.filter__max_time_date__Q1_2024
            ]
        )
        assert self.metric__cocktail_uplift in df.columns
        assert self.breakout__max_time_month in df.columns

    def test_sales_uplift_and_sold_cases_in_q1_2024(self):

        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__single_spirit_uplift, self.metric__sold_cases]),
            filters = [self.filter__brand_name__papas_pilar, self.filter__max_time_date__Q1_2024]
        )
        assert self.metric__single_spirit_uplift in df.columns
        assert self.metric__sold_cases in df.columns

        
    # def test_sales_uplift_by_month_for_papas_pilar_and_daiquiri_in_2024(self):
    #     df = self.pull_data_function(
    #         metrics = self._get_metrics([self.metric__cocktail_uplift]),
    #         breakouts = [self.breakout__max_time_month],
    #         filters = [self.filter__brand_name__papas_pilar, self.filter__ingredient_of_cocktail_name__daiquiri, self.filter__max_time_date__Q1_2024]
    #     )

    #     assert self.metric__cocktail_uplift in df.columns
    #     assert self.breakout__max_time_month in df.columns

    #     # TODO: Validate this value
    #     uplift_value = df[self.metric__cocktail_uplift].sum()
    #     self.assert_value_between_threshold(uplift_value, 0.549725604285, 0.001)


    def test_sales_uplift_by_for_canada_stiegl_in_jan_2025(self):

        df = self.pull_data_function(
            metrics = self._get_metrics([self.metric__cocktail_uplift]),
            filters = [self.filter__brand_name__stiegl, self.filter__max_time_date__jan_2025, self.filter__country__canada]
        )

        assert self.metric__cocktail_uplift in df.columns

    # No depletion data found for this test
    # def test_sales_uplift_by_brand_for_canada_erdinger_in_jan_2025(self):
    #     df = self.pull_data_function(
    #         metrics = self._get_metrics([self.metric__single_spirit_uplift]),
    #         filters = [self.filter__brand_name__erdinger, self.filter__max_time_date__jan_2025, self.filter__country__canada]
    #     )

    #     assert self.metric__single_spirit_uplift in df.columns

        
