from typing import List
import pandas as pd
import numpy as np
from ar_analytics import pull_data
from ar_analytics.helpers.utils import exit_with_status
from skill_framework import ExportData, SkillOutput
from overproof_utilities import MenuColNames, OverproofSharedFn
from overproof_visualization_utilities import render_layout

from analysis_classes.bdi_cdi_opportunity.defaults import BdiCdiInit, BdiCdiParameters, BdiCdiRunResult

class BdiCdiOpportunity:
    def __init__(self, init: BdiCdiInit):
        self.con = init.sql_exec
        self.dim_hierarchy = init.dim_hierarchy
        self.pills = init.pills
        self.metric_props = init.metric_props
        self.dim_props = init.dim_props
        self.max_prompt = init.max_prompt
        self.insight_prompt = init.insight_prompt
        self.table_viz_layout = init.table_viz_layout
        self.pull_data_func = init.df_provider.pull_data if init.df_provider and hasattr(init.df_provider, "pull_data") else pull_data
        self.helper = OverproofSharedFn()

    def run(self, parameters: BdiCdiParameters) -> BdiCdiRunResult:
        breakout = parameters.breakout
        period_filters = parameters.period_filters or []
        other_filters = parameters.other_filters or []
        brand_val = parameters.brand_filter
        cat_val = parameters.category_filter

        metric = self.helper.get_metric_prop(MenuColNames.MENU_PLACEMENTS_METRIC.value, self.metric_props)

        # Pull data
        brand_df = self.pull_data_func(
            metrics=[metric],
            breakouts=[breakout],
            filters=[{"col": MenuColNames.BRAND_NAME_COL.value, "op": "=", "val": brand_val}] + other_filters + period_filters
        )
        cat_df = self.pull_data_func(
            metrics=[metric],
            breakouts=[breakout],
            filters=[{"col": MenuColNames.PRODUCT_CATEGORY_NAME_COL.value, "op": "=", "val": cat_val}] + other_filters + period_filters
        )
        total_df = self.pull_data_func(
            metrics=[metric],
            breakouts=[breakout],
            filters=other_filters + period_filters
        )
        # Guardrail for no data
        if total_df.empty or brand_df.empty or cat_df.empty:
            exit_with_status("No data found for the given filters")

        # Rename for clarity
        total_df = total_df.rename(columns={metric["name"]: "total_placements"})
        brand_df = brand_df.rename(columns={metric["name"]: "brand_placements"})
        cat_df = cat_df.rename(columns={metric["name"]: "category_placements"})

        # Merge data
        df = total_df
        if not brand_df.empty:
            df = df.merge(brand_df[[breakout, "brand_placements"]], on=breakout, how="left")
        else:
            df["brand_placements"] = 0
        if not cat_df.empty:
            df = df.merge(cat_df[[breakout, "category_placements"]], on=breakout, how="left")
        else:
            df["category_placements"] = 0

        # Compute shares
        df["brand_share"] = df["brand_placements"] / df["total_placements"].replace({0: np.nan})
        df["category_share"] = df["category_placements"] / df["total_placements"].replace({0: np.nan})

        # Compute BDI, CDI, Opportunity Score
        df["BDI"] = df["brand_share"]
        df["CDI"] = df["category_share"]
        df["opportunity_score"] = df["CDI"] - df["BDI"]

        # Dummy recommendation
        df["recommended"] = "✅ Yes"

        # Select output columns
        table_df = df[[breakout, "BDI", "CDI", "opportunity_score", "brand_share", "category_share", "recommended"]]

        # Title and subtitle
        title = f"BDI/CDI Opportunity for {parameters.brand_filter} in {parameters.category_filter}"
        subtitle = f"{parameters.date_labels.get('start_date')} to {parameters.date_labels.get('end_date')}"

        return BdiCdiRunResult(
            table_df=table_df,
            fact_dfs=[],
            followups=[],
            title=title,
            subtitle=subtitle
        )

    def create_viz(self, run_result: BdiCdiRunResult) -> SkillOutput:
        tables = {run_result.title: run_result.table_df}
        warnings = run_result.warnings
        footnotes = {}
        general_footnote = run_result.general_footnote

        viz, insights, final_prompt, export_data = render_layout(
            tables,
            run_result.title,
            run_result.subtitle,
            run_result.fact_dfs,
            warnings,
            footnotes,
            general_footnote,
            self.max_prompt,
            self.insight_prompt,
            self.table_viz_layout
        )

        return SkillOutput(
            final_prompt=final_prompt,
            narrative=None,
            visualizations=viz,
            parameter_display_descriptions=self.pills,
            followup_questions=run_result.followups,
            export_data=[ExportData(name=name, data=df) for name, df in export_data.items()]
        )