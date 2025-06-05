from types import SimpleNamespace
from typing import List, Tuple
from ar_analytics.helpers.utils import TemplateParameterSetup, SkillPlatform, exit_with_status, Connector
from skill_framework import ParameterDisplayDescription, SkillInput

from analysis_classes.strategic_benchmark.defaults import StrategicBenchmarkInit, StrategicBenchmarkParameters
from overproof_utilities import MenuColNames

import logging
logger = logging.getLogger(__name__)

class StrategicBenchmarkTemplateParameterSetup(TemplateParameterSetup):

    def __init__(self):
        sp = SkillPlatform()
        super().__init__(sp=sp)

    def get_pills(self, metric_pills: List[str], query_filters_pills: List[str], date_labels: dict):

        start_date = date_labels.get("start_date")
        end_date = date_labels.get("end_date")
        compare_start_date = date_labels.get("compare_start_date")
        compare_end_date = date_labels.get("compare_end_date")

        pills = []

        if metric_pills:
            pills.append(ParameterDisplayDescription(key="metrics", value=f"Metrics: {self.helper.and_comma_join(metric_pills)}"))
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
        return pills

    def map_parameters(self, parameters: SkillInput) -> Tuple[StrategicBenchmarkInit, StrategicBenchmarkParameters]:

        # TODO: Remove this and utilize the default mapping
        param_dict = {"periods": [], "metrics": None, "limit_n": 10, "breakouts": None, "growth_type": None, "other_filters": [], "growth_trend": None, "calculated_metric_filters": None}
        print(f"Skill received following parameters: {parameters.arguments}")
        # Update param_dict with values from parameters.arguments if they exist
        for key in param_dict:
            if hasattr(parameters.arguments, key) and getattr(parameters.arguments, key) is not None:
                param_dict[key] = getattr(parameters.arguments, key)

        env = SimpleNamespace(**param_dict)

        if env is None:
            ValueError("env is required.")

        ## Setup DB

        database_id = self.dataset_metadata.get("database_id")
        con = Connector("db", database_id=database_id,
                                               sql_dialect=self.dataset_metadata.get("sql_dialect"),
                                               limit=self.sql_row_limit)

        _, dim_hierarchy = self.sp.data.get_dimension_hierarchy()

        # TODO: Necessary for this skill?
        # # Mapping cocktails -> ingredient of cocktails and vice versa
        # updated_filters, updated_breakouts, updated_dim_hierarchy = map_cocktails(
        #     env.breakout_parameters["query_filters"], 
        #     env.breakout_parameters["breakouts"], 
        #     env.breakout_parameters["dim_hierarchy"],
        #     env.dim_props
        # )
        # env.breakout_parameters["query_filters"] = updated_filters
        # env.breakout_parameters["breakouts"] = updated_breakouts
        # env.breakout_parameters["dim_hierarchy"] = updated_dim_hierarchy

        ## Map Env Variables

        # Get metric_props, dim_props, setting on env since the chart templates reference these

        metric_props = self.get_metric_props()
        dim_props = self.get_dimension_props()

        ## Get filters by dimension

        query_filters, query_filters_pills = self.parse_dimensions(env)

        # set growth type
        growth_type = "Y/Y" # setting as default, but keeping as a parameter in case it is changed down the line

        # Get metrics and metric pills
        DEFAULT_METRICS = [MenuColNames.MENU_PLACEMENTS_METRIC.value, MenuColNames.SOLD_9LE_METRIC.value]
        metrics = DEFAULT_METRICS
        metric_pills = self.get_metric_pills(metrics, metric_props) # TODO: Do we need to show these?

        ### Period Handling ###

        default_granularity = self.dataset_metadata.get("default_granularity")
        compare_date_warning_msg = None

        # if not self.is_period_table:
        start_date, end_date, comp_start_date, comp_end_date = self.handle_periods_and_comparison_periods(
            env.periods, growth_type, allowed_tokens=['<no_period_provided>', '<since_launch>'])

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

        sb_parameters = StrategicBenchmarkParameters(
            metrics=metrics,
            query_filters=query_filters,
            period_filters=period_filters,
            compare_date_warning_msg=compare_date_warning_msg,
            date_labels=date_labels
        )

        sb_init = StrategicBenchmarkInit(
            sql_exec=con,
            dim_hierarchy=dim_hierarchy,
            compare_date_warning_msg=compare_date_warning_msg,
            pills=self.get_pills(metric_pills, query_filters_pills, date_labels),
            metric_props=metric_props,
            dim_props=dim_props,
            max_prompt=parameters.arguments.max_prompt,
            insight_prompt=parameters.arguments.insight_prompt,
            table_viz_layout=parameters.arguments.table_viz_layout
        )

        return sb_init, sb_parameters
    