from types import SimpleNamespace
from typing import Tuple, List
from ar_analytics.helpers.utils import TemplateParameterSetup, SkillPlatform, exit_with_status, Connector, NO_LIMIT_N
from skill_framework import SkillInput, ParameterDisplayDescription
from overproof_utilities import MenuColNames
from analysis_classes.bdi_cdi_opportunity.defaults import BdiCdiInit, BdiCdiParameters

from overproof_data_provider import DataProvider

class BdiCdiTemplateParameterSetup(TemplateParameterSetup):
    def __init__(self):
        sp = SkillPlatform()
        super().__init__(sp=sp)

    def get_category_filter(self, brand_filter: dict, metric_props: dict) -> dict:

        df_provider = DataProvider()

        menu_placements_metric = self.helper.get_metric_prop(MenuColNames.MENU_PLACEMENTS_METRIC.value, metric_props)

        categories_df = df_provider.pull_data(
            metrics=[menu_placements_metric],
            breakouts=[MenuColNames.PRODUCT_CATEGORY_NAME_COL.value],
            filters=[brand_filter]
        )

        # In case of multiple categories, get the category with the highest menu placements
        categories_df = categories_df.sort_values(by=MenuColNames.MENU_PLACEMENTS_METRIC.value, ascending=False)

        unique_categories = categories_df[MenuColNames.PRODUCT_CATEGORY_NAME_COL.value].unique().tolist()

        if not unique_categories:
            exit_with_status(f"No categories found for the given brand: {brand_filter.get('val')}")

        return {"col": MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, "op": "IN", "val": unique_categories[0]}

    def get_pills(self, brand_filter: str, category_filter: str, breakout_pills: List[str], query_filters_pills: List[str], date_labels: dict, limit_n: int):

        start_date = date_labels.get("start_date")
        end_date = date_labels.get("end_date")
        compare_start_date = date_labels.get("compare_start_date")
        compare_end_date = date_labels.get("compare_end_date")

        pills = []

        if brand_filter:
            pills.append(ParameterDisplayDescription(key="brand", value=f"Brand: {brand_filter}"))
        if category_filter:
            pills.append(ParameterDisplayDescription(key="category", value=f"Category: {category_filter}"))
        if breakout_pills:
            pills.append(ParameterDisplayDescription(key="breakout", value=f"Breakout: {self.helper.and_comma_join(breakout_pills)}"))
        if query_filters_pills:
            pills.append(ParameterDisplayDescription(key="filters", value=f"Filter: {self.helper.and_comma_join(query_filters_pills)}"))
        if start_date and end_date:
            if start_date == end_date:
                pills.append(ParameterDisplayDescription(key="period", value=f"Period: {start_date}"))
            else:
                pills.append(ParameterDisplayDescription(key="period", value=f"Period: {start_date} to {end_date}"))
        if compare_start_date and compare_end_date:
            if compare_start_date == compare_end_date:
                pills.append(ParameterDisplayDescription(key="compare_period", value=f"Compare Period: {compare_start_date}"))
            else:
                pills.append(ParameterDisplayDescription(key="compare_period", value=f"Compare Period: {compare_start_date} to {compare_end_date}"))
        if limit_n:
            pills.append(ParameterDisplayDescription(key="limit_n", value=f"Top {str(limit_n)}"))
        return pills

    def map_parameters(self, parameters: SkillInput) -> Tuple[BdiCdiInit, BdiCdiParameters]:

        # TODO: Remove this and utilize the default mapping
        param_dict = {"periods": [], "other_filters": [], "brand_filter": None, "category_filter": None, "breakout": None, "limit_n": 20}
        print(f"Skill received following parameters: {parameters.arguments}")
        # Update param_dict with values from parameters.arguments if they exist
        for key in param_dict:
            if hasattr(parameters.arguments, key) and getattr(parameters.arguments, key) is not None:
                param_dict[key] = getattr(parameters.arguments, key)

        env = SimpleNamespace(**param_dict)

        if env is None:
            ValueError("env is required.")

        brand = env.brand_filter
        category = env.category_filter

        if not brand:
            exit_with_status("Please provide a brand to analyze.")
        else:
            brand_filter = {"col": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": brand}

        if not category:
            category_filter = self.get_category_filter(brand_filter, self.get_metric_props())
        else:
            category_filter = {"col": MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, "op": "=", "val": category}

        # Setup DB connection
        database_id = self.dataset_metadata.get("database_id")
        con = Connector("db", database_id=database_id,
                        sql_dialect=self.dataset_metadata.get("sql_dialect"),
                        limit=self.sql_row_limit)
        _, dim_hierarchy = self.sp.data.get_dimension_hierarchy()

        if not env.breakout:
            exit_with_status("Please provide a breakout.")

        if env.breakout and type(env.breakout) is list:
            env.breakout = env.breakout[0]

        ## Parse breakout dims to the sql columns
        breakouts, breakout_pills = self.parse_breakout_dims([env.breakout])
        breakout = breakouts[0]

        # TODO: Remove this, currently venue county isn't in the data
        if env.breakout == MenuColNames.VENUE__COUNTY_COL.value:
            exit_with_status("Venue county breakout is not available in the data yet.")

        if breakout not in [MenuColNames.STATE_NAME_COL.value, MenuColNames.VENUE__COUNTY_COL.value]:
            exit_with_status(f"Breakout must be {MenuColNames.STATE_NAME_COL.value} or {MenuColNames.VENUE__COUNTY_COL.value}.")

        ## Get filters by dimension
        query_filters, query_filters_pills = self.parse_dimensions(env) # TODO: Remove brand and product filters placed here?

        ### Period Handling ###

        default_granularity = self.dataset_metadata.get("default_granularity")
        compare_date_warning_msg = None

        # if not self.is_period_table:
        start_date, end_date, comp_start_date, comp_end_date = self.handle_periods_and_comparison_periods(
            env.periods, None, allowed_tokens=['<no_period_provided>', '<since_launch>'])

        # date/period column metadata. Assumes the date column is a date type
        period_col = self.get_period_col()

        if not period_col:
            exit_with_status("A date column must be provided.")

        # create period filters using start date and end date, and comparison start and end dates
        period_filters = []

        if start_date and end_date:
            period_filters.append(
                {"col": period_col, "op": "BETWEEN", "val": f"'{start_date}' AND '{end_date}'"}
            )

        if comp_start_date and comp_end_date:
            period_filters.append(
                {"col": period_col, "op": "BETWEEN", "val": f"'{comp_start_date}' AND '{comp_end_date}'"}
            )

            if self.is_date_range_completely_out_of_bounds(comp_start_date, comp_end_date):
                compare_date_warning_msg = "Data for the full comparison period is unavailable, preventing growth calculation. This gap might impact the analysis results and insights."
            elif self.is_date_range_partially_out_of_bounds(comp_start_date, comp_end_date):
                compare_date_warning_msg = "Data is only avaiable for partial comparison period. This gap might impact the analysis results and insights."

        # format dates after adding them to the period filters

        start_date = self.helper.format_date_from_time_granularity(start_date, default_granularity)
        end_date = self.helper.format_date_from_time_granularity(end_date, default_granularity)
        comp_start_date = self.helper.format_date_from_time_granularity(comp_start_date, default_granularity)
        comp_end_date = self.helper.format_date_from_time_granularity(comp_end_date, default_granularity)

        date_labels = {
            "start_date": start_date, 
            "end_date": end_date, 
            "compare_start_date": comp_start_date,
            "compare_end_date": comp_end_date
        }

        limit_n = None

        # convert limit_n to an int
        if hasattr(env, "limit_n") and env.limit_n:
            if env.limit_n == NO_LIMIT_N:
                limit_n = None
            else:
                limit_n = self.convert_to_int(env.limit_n)

        bdi_init = BdiCdiInit(
            sql_exec=con,
            dim_hierarchy=dim_hierarchy,
            pills=self.get_pills(brand, category, breakout_pills, query_filters_pills, date_labels, limit_n),
            metric_props=self.get_metric_props(),
            dim_props=self.get_dimension_props(),
            max_prompt=parameters.arguments.max_prompt,
            insight_prompt=parameters.arguments.insight_prompt,
            table_viz_layout=parameters.arguments.table_viz_layout,
            compare_date_warning_msg=compare_date_warning_msg
        )
        bdi_params = BdiCdiParameters(
            brand_filter=brand_filter,
            category_filter=category_filter,
            breakout=breakout,
            other_filters=query_filters,
            period_filters=period_filters,
            date_labels=date_labels,
            limit_n=limit_n
        )

        return bdi_init, bdi_params