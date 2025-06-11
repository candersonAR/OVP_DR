from types import SimpleNamespace
from typing import Tuple, List
from ar_analytics.helpers.utils import TemplateParameterSetup, SkillPlatform, exit_with_status, Connector
from skill_framework import SkillInput, ParameterDisplayDescription
from overproof_utilities import MenuColNames
from analysis_classes.bdi_cdi_opportunity.defaults import BdiCdiInit, BdiCdiParameters

class BdiCdiTemplateParameterSetup(TemplateParameterSetup):
    def __init__(self):
        sp = SkillPlatform()
        super().__init__(sp=sp)

    def map_parameters(self, parameters: SkillInput) -> Tuple[BdiCdiInit, BdiCdiParameters]:
        print(f"Skill received parameters: {parameters.arguments}")

        brand_list = getattr(parameters.arguments, "brand_filter", []) or []
        category_list = getattr(parameters.arguments, "category_filter", []) or []
        breakout = getattr(parameters.arguments, "breakout", None)
        other_filters = getattr(parameters.arguments, "other_filters", []) or []
        periods = getattr(parameters.arguments, "periods", []) or []

        if len(brand_list) != 1:
            exit_with_status("Please provide exactly one brand in brand_filter.")
        if len(category_list) != 1:
            exit_with_status("Please provide exactly one category in category_filter.")

        brand = brand_list[0]
        category = category_list[0]

        if breakout not in ["state_name", "venue__county"]:
            exit_with_status("Breakout must be 'state_name' or 'venue__county'.")

        # Build query filters
        brand_filter = {"col": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": brand}
        category_filter = {"col": MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, "op": "=", "val": category}
        query_filters = [brand_filter, category_filter] + other_filters

        # Handle periods
        default_granularity = self.dataset_metadata.get("default_granularity")
        start_date, end_date, _, _ = self.handle_periods_and_comparison_periods(periods, "")
        period_col = self.get_period_col()
        if not period_col:
            exit_with_status("A date column must be provided.")

        period_filters: List[dict] = []
        if start_date and end_date:
            period_filters.append(
                {"col": period_col, "op": "BETWEEN", "val": f"'{start_date}' AND '{end_date}'"}
            )

        # Format date labels
        start_label = self.helper.format_date_from_time_granularity(start_date, default_granularity)
        end_label = self.helper.format_date_from_time_granularity(end_date, default_granularity)
        date_labels = {"start_date": start_label, "end_date": end_label}

        # Build pills
        pills: List[ParameterDisplayDescription] = []
        pills.append(ParameterDisplayDescription(key="brand", value=f"Brand: {brand}"))
        pills.append(ParameterDisplayDescription(key="category", value=f"Category: {category}"))
        pills.append(ParameterDisplayDescription(key="breakout", value=f"Breakout: {breakout}"))
        if start_label == end_label:
            pills.append(ParameterDisplayDescription(key="period", value=f"Period: {start_label}"))
        else:
            pills.append(ParameterDisplayDescription(key="period", value=f"Period: {start_label} to {end_label}"))

        # Setup DB connection
        database_id = self.dataset_metadata.get("database_id")
        con = Connector("db", database_id=database_id,
                        sql_dialect=self.dataset_metadata.get("sql_dialect"),
                        limit=self.sql_row_limit)
        _, dim_hierarchy = self.sp.data.get_dimension_hierarchy()

        bdi_init = BdiCdiInit(
            sql_exec=con,
            dim_hierarchy=dim_hierarchy,
            pills=pills,
            metric_props=self.get_metric_props(),
            dim_props=self.get_dimension_props(),
            max_prompt=parameters.arguments.max_prompt,
            insight_prompt=parameters.arguments.insight_prompt,
            table_viz_layout=parameters.arguments.table_viz_layout
        )
        bdi_params = BdiCdiParameters(
            brand_filter=brand_filter,
            category_filter=category_filter,
            breakout=breakout,
            other_filters=other_filters,
            period_filters=period_filters,
            date_labels=date_labels
        )

        return bdi_init, bdi_params