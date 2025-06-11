from typing import List, Optional, Tuple
import pandas as pd
import numpy as np
from ar_analytics import pull_data
from ar_analytics.helpers.utils import exit_with_status, old_get_date_label_str, old_get_filters_headline
from skill_framework import ExportData, SkillOutput
from overproof_utilities import MenuColNames, OverproofSharedFn
from overproof_visualization_utilities import render_layout

from analysis_classes.bdi_cdi_opportunity.defaults import BdiCdiInit, BdiCdiParameters, BdiCdiRunResult, FactColumnFormat

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
        self.compare_date_warning_msg = init.compare_date_warning_msg

        self.helper = OverproofSharedFn()
        self.notes = []

    def get_title_and_subtitle(self, parameters: BdiCdiParameters) -> Tuple[str, str]:

        title = old_get_filters_headline(
            [parameters.brand_filter, parameters.category_filter],
            headline_seperator=", ",
            metric_props=self.metric_props,
            dim_props=self.dim_props
        )

        query_filters_title = old_get_filters_headline(
            parameters.other_filters,
            headline_seperator=", ",
            metric_props=self.metric_props,
            dim_props=self.dim_props
        )

        title = f"BDI/CDI Opportunity for {title}"

        if query_filters_title:
            title = f"{title} • {query_filters_title}"

        breakout_prop = self.helper.get_dimension_prop(parameters.breakout, self.dim_props)

        subtitle = f"Broken out by {breakout_prop.get('label', parameters.breakout)}"
        subtitle = f"{subtitle}{old_get_date_label_str(parameters.date_labels, prefix=' • ')}"

        return title, subtitle
    
    def rank_df_and_limit_to_top_n(self, df: pd.DataFrame, sort_col: str, limit_n: Optional[int] = None) -> pd.DataFrame:
        """
        Rank the dataframe by the given metric and breakout.
        """

        if not limit_n:
            return df
        
        df = df.sort_values(by=sort_col, ascending=False)

        if df.shape[0] > limit_n:
            self.notes.append(f"Top {limit_n} by {sort_col} shown, {df.shape[0] - limit_n} not shown")

        return df.head(limit_n)

    def get_market_share_df(self, share_metrics: List[dict], breakout: str, brand_filter: dict, cat_filter: dict, other_filters: list, period_filters: list) -> pd.DataFrame:

        component_metrics = []

        for share_metric in share_metrics:
            component_metric_name = share_metric.get("component_metric")
            component_metric = self.helper.get_metric_prop(component_metric_name, self.metric_props)
            if not component_metric_name:
                exit_with_status(f"No component metric found for the given share metric: {share_metric.get('name')}")
            component_metrics.append(component_metric)

        brand_val = brand_filter.get("val")
        cat_val = cat_filter.get("val")

        # Pull data
        brand_df = self.pull_data_func(
            metrics=component_metrics,
            breakouts=[breakout],
            filters=[brand_filter] + other_filters + period_filters
        )
        cat_df = self.pull_data_func(
            metrics=component_metrics,
            breakouts=[breakout],
            filters=[cat_filter] + other_filters + period_filters
        )
        total_df = self.pull_data_func(
            metrics=component_metrics,
            breakouts=[breakout],
            filters=other_filters + period_filters
        )

        if brand_df.empty:
            exit_with_status(f"No data found for the given brand filter: {brand_val}")
        if cat_df.empty:
            exit_with_status(f"No data found for the given category filter: {cat_val}")
        if total_df.empty:
            exit_with_status(f"No data found for the given filters")

        # Rename for clarity
        total_df = total_df.rename(columns={component_metric["name"]: f"total_{component_metric['name']}" for component_metric in component_metrics})
        brand_df = brand_df.rename(columns={component_metric["name"]: f"brand_{component_metric['name']}" for component_metric in component_metrics})
        cat_df = cat_df.rename(columns={component_metric["name"]: f"category_{component_metric['name']}" for component_metric in component_metrics})

        # Merge data
        df = total_df
        if not brand_df.empty:
            brand_cols = [f"brand_{component_metric['name']}" for component_metric in component_metrics]
            df = df.merge(brand_df[[breakout, *brand_cols]], on=breakout, how="left")
        else:
            for component_metric in component_metrics:
                df[f"brand_{component_metric['name']}"] = 0
        if not cat_df.empty:
            cat_cols = [f"category_{component_metric['name']}" for component_metric in component_metrics]
            df = df.merge(cat_df[[breakout, *cat_cols]], on=breakout, how="left")
        else:
            for component_metric in component_metrics:
                df[f"category_{component_metric['name']}"] = 0
    
        # Compute shares
        for share_metric in share_metrics:
            component_metric_name = share_metric.get("component_metric")
            df[f"brand_{share_metric['name']}"] = df[f"brand_{component_metric_name}"].div(
                df[f"total_{component_metric_name}"].replace(0, np.nan),
                fill_value=0
            )
            df[f"category_{share_metric['name']}"] = df[f"category_{component_metric_name}"].div(
                df[f"total_{component_metric_name}"].replace(0, np.nan),
                fill_value=0
            )
            df = df.drop(columns=[f"brand_{component_metric_name}", f"category_{component_metric_name}", f"total_{component_metric_name}"])

        return df
    
    def calculate_bdi_cdi_opportunity_score(self, df: pd.DataFrame, menu_placements_share_metric: dict, venue_share_metric: dict) -> pd.DataFrame:

        # TODO: Fill in NaNs with 0, ie where the venue share is 0, or not?
        df["BDI"] = df[f"brand_{menu_placements_share_metric['name']}"].div(
            df[f"brand_{venue_share_metric['name']}"].replace(0, np.nan),
            fill_value=0
        )
        df["CDI"] = df[f"category_{menu_placements_share_metric['name']}"].div(
            df[f"category_{venue_share_metric['name']}"].replace(0, np.nan),
            fill_value=0
        )
        df["opportunity_score"] = df["CDI"] - df["BDI"]

        return df
    
    def get_reccomendation(self, df: pd.DataFrame) -> pd.DataFrame:
        # Define thresholds for high/low bdi/cdi categorization 
        THRESHOLD = 1  # Above 1 is considered high

        # Create recommendation based on BDI and CDI values
        conditions = [
            # High CDI / Low BDI - White space, Target for expansion
            (df['CDI'] > THRESHOLD) & (df['BDI'] < THRESHOLD),
            # High CDI / High BDI - Stronghold, Defend & optimize
            (df['CDI'] > THRESHOLD) & (df['BDI'] > THRESHOLD),
            # Low CDI / High BDI - Overweight risk, Rebalance or reduce
            (df['CDI'] < THRESHOLD) & (df['BDI'] > THRESHOLD),
            # Low CDI / Low BDI - Low value, Deprioritize
            (df['CDI'] < THRESHOLD) & (df['BDI'] < THRESHOLD)
        ]
        
        choices = [
            "Target for expansion",
            "Defend & optimize",
            "Rebalance or reduce",
            "Deprioritize"
        ]
        
        df["recommended"] = np.select(conditions, choices, default="Monitor")
        
        return df

    def run(self, parameters: BdiCdiParameters) -> BdiCdiRunResult:
        breakout = parameters.breakout
        period_filters = parameters.period_filters or []
        other_filters = parameters.other_filters or []
        brand_filter = parameters.brand_filter
        cat_filter = parameters.category_filter

        menu_placements_share_metric = self.helper.get_metric_prop(MenuColNames.MENU_PLACEMENTS_SHARE_METRIC.value, self.metric_props)
        venue_share_metric = self.helper.get_metric_prop(MenuColNames.VENUE_PLACEMENTS_SHARE_METRIC.value, self.metric_props)

        market_share_df = self.get_market_share_df(
            [menu_placements_share_metric, venue_share_metric], 
            breakout, 
            brand_filter, 
            cat_filter, 
            other_filters, 
            period_filters
        )

        market_share_df = self.calculate_bdi_cdi_opportunity_score(market_share_df, menu_placements_share_metric, venue_share_metric)
        market_share_df = self.get_reccomendation(market_share_df)

        table_df = market_share_df[[breakout, "BDI", "CDI", "opportunity_score", f"brand_{menu_placements_share_metric['name']}", f"category_{menu_placements_share_metric['name']}", "recommended"]]
        table_df = self.rank_df_and_limit_to_top_n(table_df, "opportunity_score", parameters.limit_n)

        title, subtitle = self.get_title_and_subtitle(parameters)

        # Prepare formatted facts dataframe for narrative insights
        fact_dfs = []
        formatted_df = self.get_facts_df(table_df, menu_placements_share_metric, breakout, brand_filter, cat_filter, other_filters)
        fact_dfs.append(formatted_df)

        if self.notes:
            self.notes.append(pd.DataFrame({"Note to the assistant:": self.notes}))
        
        return BdiCdiRunResult(
            table_df=formatted_df,
            fact_dfs=fact_dfs,
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
    
    def get_facts_df(self, table_df: pd.DataFrame, share_metric: dict, breakout: str, brand_filter: dict, cat_filter: dict, query_filters: List[dict]) -> pd.DataFrame:
        """
        Format numeric columns of the BDI/CDI table for narrative facts.
        """
        facts_df = table_df.copy()

        format_map = {
            f"brand_{share_metric['name']}": share_metric.get("fmt", ",.2f"),
            f"category_{share_metric['name']}": share_metric.get("fmt", ",.2f"),
            "BDI": ",.2f",
            "CDI": ",.2f",
            "opportunity_score": ",.2f"
        }

        signed_cols = ["opportunity_score"]

        for col, fmt in format_map.items():
            if col in facts_df.columns:
                signed = col in signed_cols
                facts_df[col] = facts_df[col].apply(
                    lambda x: self.helper.get_formatted_num(x, fmt, signed=signed)
                )   

        breakout_prop = self.helper.get_dimension_prop(breakout, self.dim_props)
        breakout_label = breakout_prop.get("label", breakout)

        brand_val = brand_filter.get("val").title()
        cat_val = cat_filter.get("val").title()

        rename_map = {
            breakout: breakout_label,
            f"brand_{share_metric['name']}": f"{brand_val} {share_metric.get('label', share_metric['name'])}",
            f"category_{share_metric['name']}": f"{cat_val} {share_metric.get('label', share_metric['name'])}",
            "BDI": "BDI",
            "CDI": "CDI",
            "opportunity_score": "Opportunity Score",
            "recommended": "Recommended?"
        }
        facts_df = facts_df.rename(columns=rename_map)

        metric_names = [f"brand_{share_metric['name']}", f"category_{share_metric['name']}", "BDI", "CDI", "opportunity_score"]

        facts_df.max_metadata.set_filters(query_filters)
        facts_df.max_metadata.set_measures(metric_names)
        facts_df.max_metadata.set_description(f"{', '.join(metric_names)} broken out by {breakout}")

        return facts_df