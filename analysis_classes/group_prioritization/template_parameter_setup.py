from types import SimpleNamespace
from typing import List, Tuple
from ar_analytics.helpers.utils import TemplateParameterSetup, SkillPlatform, exit_with_status, Connector
from skill_framework import ParameterDisplayDescription, SkillInput

from analysis_classes.group_prioritization.defaults import DEFAULT_METRICS, DEFAULT_DIMENSIONS, DEFAULT_PERIOD, GroupPrioritizationInit, GroupPrioritizationParameters
from overproof_utilities import MenuColNames

import logging
logger = logging.getLogger(__name__)

class GroupPrioritizationTemplateParameterSetup(TemplateParameterSetup):

    def __init__(self):
        sp = SkillPlatform()
        super().__init__(sp=sp)

    def get_pills(self, metric_pills: List[str], query_filters_pills: List[str], 
                  date_labels: dict, dimensions_pills: List[str], brand_name: str, 
                  benchmark_name: str, growth_type: str) -> List[ParameterDisplayDescription]:
        """Generate parameter display pills"""

        start_date = date_labels.get("start_date")
        end_date = date_labels.get("end_date")
        compare_start_date = date_labels.get("compare_start_date")
        compare_end_date = date_labels.get("compare_end_date")

        pills = []

        # Brand comparison pill
        pills.append(ParameterDisplayDescription(
            key="comparison", 
            value=f"Comparing: {brand_name} vs. {benchmark_name}"
        ))

        if query_filters_pills:
            pills.append(ParameterDisplayDescription(
                key="filters", 
                value=f"Filter: {self.helper.and_comma_join(query_filters_pills)}"
            ))
            
        if start_date and end_date:
            if start_date == end_date:
                pills.append(ParameterDisplayDescription(
                    key="period", 
                    value=f"Period: {start_date}"
                ))
            else:
                pills.append(ParameterDisplayDescription(
                    key="period", 
                    value=f"Period: {start_date} to {end_date}"
                ))
                
        if compare_start_date and compare_end_date:
            if compare_start_date == compare_end_date:
                pills.append(ParameterDisplayDescription(
                    key="compare_period", 
                    value=f"Compare Period: {compare_start_date}"
                ))
            else:
                pills.append(ParameterDisplayDescription(
                    key="compare_period", 
                    value=f"Compare Period: {compare_start_date} to {compare_end_date}"
                ))
                
        if growth_type and growth_type != "None":
            pills.append(ParameterDisplayDescription(
                key="growth_type", 
                value=f"Growth Type: {growth_type}"
            ))
            
        return pills

    def extract_brand_name(self, other_filters: List[dict]) -> str:
        """Extract the brand filter from other_filters and return filter + brand name"""
        
        brand_filters = [f for f in other_filters if f["dim"] == MenuColNames.BRAND_NAME_COL.value]
        
        if not brand_filters:
            exit_with_status("Must provide a brand filter in the filters.")
        
        if len(brand_filters) > 1:
            exit_with_status("Multiple brand filters found. Please provide only one brand filter.")
        
        brand_filter = brand_filters[0]
        
        # Handle different filter value formats
        if isinstance(brand_filter['val'], list):
            if len(brand_filter['val']) > 1:
                exit_with_status("Multiple brands selected. Please provide only one brand filter.")
            brand_name = brand_filter['val'][0]
        else:
            brand_name = brand_filter['val']

        return brand_name

    def map_parameters(self, parameters: SkillInput) -> Tuple[GroupPrioritizationInit, GroupPrioritizationParameters]:
        """Map skill input parameters to analysis parameters"""

        # Set defaults
        param_dict = {
            "periods": DEFAULT_PERIOD if not parameters.arguments.periods else parameters.arguments.periods,
            "benchmark_brand": parameters.arguments.benchmark_brand,
            "growth_type": parameters.arguments.growth_type,
            "other_filters": parameters.arguments.other_filters or []
        }

        env = SimpleNamespace(**param_dict)

        # Validate required parameters
        if not env.benchmark_brand:
            exit_with_status("Must provide a benchmark brand for comparison.")

        brand_name = self.extract_brand_name(env.other_filters)

        # Extract brand filter from other_filters
        query_filters, query_filters_pills = self.parse_dimensions(SimpleNamespace(other_filters=env.other_filters))
        updated_filters = [filter if filter['col'] != MenuColNames.BRAND_NAME_COL.value else {
            "col": MenuColNames.BRAND_NAME_COL.value,
            "op": "in",
            "val":  [env.benchmark_brand, brand_name]
        } for filter in query_filters]

        # Setup DB connection
        database_id = self.dataset_metadata.get("database_id")
        con = Connector(
            "db", 
            database_id=database_id,
            sql_dialect=self.dataset_metadata.get("sql_dialect"),
            limit=self.sql_row_limit
        )

        _, dim_hierarchy = self.sp.data.get_dimension_hierarchy()

        # Get metric and dimension properties
        metric_props = self.get_metric_props()
        dim_props = self.get_dimension_props()

        # Parse filters (excluding the brand filter which we handle separately)
        # other_filters_without_brand = [f for f in query_filters if f['col'] != MenuColNames.BRAND_NAME_COL.value]

        # Set growth type
        growth_type = env.growth_type

        # Get metrics
        metrics = [self.helper.get_metric_prop(metric, metric_props) for metric in DEFAULT_METRICS]
        metric_pills = self.get_metric_pills(DEFAULT_METRICS, metric_props)

        # Get dimensions
        dimensions, dimensions_pills = self.parse_breakout_dims(DEFAULT_DIMENSIONS)

        # Period handling
        default_granularity = self.dataset_metadata.get("default_granularity")
        compare_date_warning_msg = None

        start_date, end_date, comp_start_date, comp_end_date = self.handle_periods_and_comparison_periods(
            env.periods, growth_type, allowed_tokens=['<no_period_provided>', '<since_launch>']
        )

        # Get period column
        period_col = self.get_period_col()
        if not period_col:
            exit_with_status("A date column must be provided.")

        # Create period filters
        period_filters = []
        if start_date and end_date:
            period_filters.append({
                "col": period_col, 
                "op": "BETWEEN", 
                "val": f"'{start_date}' AND '{end_date}'"
            })

        if comp_start_date and comp_end_date:
            period_filters.append({
                "col": period_col, 
                "op": "BETWEEN", 
                "val": f"'{comp_start_date}' AND '{comp_end_date}'"
            })

            if self.is_date_range_completely_out_of_bounds(comp_start_date, comp_end_date):
                compare_date_warning_msg = "Data for the full comparison period is unavailable, preventing growth calculation."
                # Can't calculate growth, so only use current period
                period_filters = period_filters[:1]
            elif self.is_date_range_partially_out_of_bounds(comp_start_date, comp_end_date):
                compare_date_warning_msg = "Data is only available for partial comparison period. This gap might impact the analysis results."

        # Format dates for display
        start_date = self.helper.format_date_from_time_granularity(start_date, default_granularity)
        end_date = self.helper.format_date_from_time_granularity(end_date, default_granularity)
        comp_start_date = self.helper.format_date_from_time_granularity(comp_start_date, default_granularity) if comp_start_date else None
        comp_end_date = self.helper.format_date_from_time_granularity(comp_end_date, default_granularity) if comp_end_date else None

        date_labels = {
            "start_date": start_date,
            "end_date": end_date,
            "compare_start_date": comp_start_date,
            "compare_end_date": comp_end_date
        }

        # Create parameter objects
        gp_parameters = GroupPrioritizationParameters(
            metrics=metrics,
            dimensions=dimensions,
            period=env.periods,
            period_filters=period_filters,
            brand_name=brand_name,
            benchmark_brand=env.benchmark_brand,
            other_filters=updated_filters,
            growth_type=growth_type,
            date_labels=date_labels
        )

        gp_init = GroupPrioritizationInit(
            sql_exec=con,
            dim_hierarchy=dim_hierarchy,
            compare_date_warning_msg=compare_date_warning_msg,
            pills=self.get_pills(
                metric_pills, 
                query_filters_pills, 
                date_labels, 
                dimensions_pills,
                brand_name,
                env.benchmark_brand,
                growth_type
            ),
            metric_props=metric_props,
            dim_props=dim_props,
            max_prompt=parameters.arguments.max_prompt,
            insight_prompt=parameters.arguments.insight_prompt,
            table_viz_layout=parameters.arguments.table_viz_layout
        )

        return gp_init, gp_parameters