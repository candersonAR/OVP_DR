from typing import List, Optional, Tuple
import pandas as pd
import numpy as np
from ar_analytics import pull_data
from ar_analytics.helpers.utils import old_get_filters_headline, old_get_date_label_str, PreQueryOperator, exit_with_status, is_filter_token, OldDimensionHierarchy
from skill_framework import ExportData, SkillOutput

from analysis_classes.strategic_benchmark.defaults import DEFAULT_METRIC_GROUP_MAPPING, StrategicBenchmarkCustomMetrics, StrategicBenchmarkInit, StrategicBenchmarkParameters, StrategicBenchmarkRunResult
from overproof_utilities import MenuColNames, OverproofSharedFn, calculate_market_share_denominator
from overproof_visualization_utilities import render_layout

# Do not remove, pulls in max_metadata on all pandas DFs
import answer_rocket

class StrategicBenchmark:
    def __init__(self, init: StrategicBenchmarkInit):

        self.con = init.sql_exec
        self.compare_date_warning_msg = init.compare_date_warning_msg
        self.pills = init.pills
        self.metric_props = init.metric_props
        self.dim_props = init.dim_props

        if not init.dim_hierarchy:
            raise exit_with_status("Dim Hierarchy not provided for share metrics")
        else:
            self.dim_hierarchy = OldDimensionHierarchy(init.dim_hierarchy)

        self.max_prompt = init.max_prompt
        self.insight_prompt = init.insight_prompt
        self.table_viz_layout = init.table_viz_layout

        self.pull_data_func = init.df_provider.pull_data if init.df_provider and hasattr(init.df_provider, "pull_data") else pull_data

        self.helper = OverproofSharedFn()
        self.notes = []

        self.quantiles = [.25, 0.3, .5, .75, .9]
        self.quantile_labels = ["cat /overall p25", "cat /overall p30", "cat /overall p50", "cat /overall p75", "cat /overall p90"]
        self.benchmark_quantile_col = self.quantile_labels[1]

        self.aggressive_goal_col = "Agressive Goal"
        self.benchmark_goal_col = "Benchmark Goal"

    def pivot_to_metrics_on_rows(self, df: pd.DataFrame, breakout_dim: str) -> pd.DataFrame:

        subject_df = df.set_index(breakout_dim).rename_axis(None, axis=0)
        subject_df = subject_df.T
        return subject_df
    
    def merge_on_index(self, df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
        
        return df1.merge(df2, left_index=True, right_index=True, how='left')
    
    def get_warning_messages(self):

        warning_messages = []

        # if self.hit_row_limit:
        #     msg = f'The following analysis has been limited to {self.helper.get_formatted_num(self.con.limit, ",.0f")} rows which may impact the accuracy of the observations made.'
        #     warning_messages.append(msg)

        if self.compare_date_warning_msg:
            warning_messages.append(self.compare_date_warning_msg)

        warning_message = ' '.join(warning_messages)
        if warning_message:
            warning_message = f"⚠ {warning_message}"

        return warning_message
    
    def get_breakout_data(self, 
        metrics: List[dict], 
        breakout: Optional[str] = None, 
        query_filters: List[dict] = None
    ) -> pd.DataFrame:
        
        if not query_filters:
            query_filters = []

        breakouts = [breakout] if breakout else []

        dfs = []

        # get metrics that can be pulled in a single pull, ie don't require additional filters or logic

        first_pull_metrics = [
            metric for metric in metrics 
            if metric['name'].lower() in [
                MenuColNames.MENU_PLACEMENTS_METRIC.value.lower(),
                MenuColNames.VENUE_PLACEMENTS_METRIC.value.lower(),
                MenuColNames.STATE_MENTIONS_METRIC.value.lower(),
                MenuColNames.POSTAL_CODE_MENTIONS_METRIC.value.lower()
            ]
        ]

        breakout_df = self.pull_data_func(
            metrics=first_pull_metrics,
            breakouts=breakouts,
            filters=query_filters
        )

        if not breakout_df.empty:
            dfs.append(breakout_df)

        # get single spirit and cocktail mentions, average monthly mentions
        menu_placement_metric = self.helper.get_metric_prop(MenuColNames.MENU_PLACEMENTS_METRIC.value, self.metric_props)
        cocktail_mentions_metric = [metric for metric in metrics if metric['name'].lower() == StrategicBenchmarkCustomMetrics.COCKTAIL_MENTIONS.value.lower()]
        single_spirit_mentions_metric = [metric for metric in metrics if metric['name'].lower() == StrategicBenchmarkCustomMetrics.SINGLE_SPIRIT_MENTIONS.value.lower()]
        average_monthly_mentions_metric = [metric for metric in metrics if metric['name'].lower() == StrategicBenchmarkCustomMetrics.AVERAGE_MONTHLY_MENTIONS.value.lower()]
        menu_placement_share_metric = [metric for metric in metrics if metric['name'].lower() == MenuColNames.MENU_PLACEMENTS_SHARE_METRIC.value.lower()]

        if cocktail_mentions_metric:

            cocktail_mentions_filters = query_filters + [
                {
                    "col": MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value,
                    "op": PreQueryOperator.NOT_NULL.value,
                    "val": None
                }
            ]

            cocktail_mentions_df = self.pull_data_func(
                metrics=[menu_placement_metric],
                breakouts=breakouts,
                filters=cocktail_mentions_filters
            )

            cocktail_mentions_df = cocktail_mentions_df.rename(columns={
                menu_placement_metric['name']: StrategicBenchmarkCustomMetrics.COCKTAIL_MENTIONS.value
            })

            if not cocktail_mentions_df.empty:
                dfs.append(cocktail_mentions_df)

        if single_spirit_mentions_metric:

            single_spirit_mentions_filters = query_filters + [
                {
                    "col": MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value,
                    "op": PreQueryOperator.NULL.value,
                    "val": None
                }
            ]

            single_spirit_mentions_df = self.pull_data_func(
                metrics=[menu_placement_metric],
                breakouts=breakouts,
                filters=single_spirit_mentions_filters
            )

            single_spirit_mentions_df = single_spirit_mentions_df.rename(columns={
                menu_placement_metric['name']: StrategicBenchmarkCustomMetrics.SINGLE_SPIRIT_MENTIONS.value
            })

            if not single_spirit_mentions_df.empty:
                dfs.append(single_spirit_mentions_df)

        if average_monthly_mentions_metric:

            month_col = MenuColNames.MAX_TIME_MONTH_COL.value
            average_monthly_breakouts = [month_col] + (breakouts if breakouts else [])

            average_monthly_mentions_df = self.pull_data_func(
                metrics=[menu_placement_metric],
                breakouts=average_monthly_breakouts,
                filters=query_filters
            )

            # get the monthly average for each breakout
            if breakouts:
                average_monthly_mentions_df = average_monthly_mentions_df.groupby(breakouts).mean().reset_index()
            else:
                average_monthly_mentions_df = average_monthly_mentions_df.groupby(lambda x: True).mean().reset_index(drop=True)

            average_monthly_mentions_df = average_monthly_mentions_df.rename(columns={
                menu_placement_metric['name']: StrategicBenchmarkCustomMetrics.AVERAGE_MONTHLY_MENTIONS.value
            })

            if not average_monthly_mentions_df.empty:
                dfs.append(average_monthly_mentions_df)

        if menu_placement_share_metric and not breakout_df.empty:

            keep_cols = breakouts + [MenuColNames.MENU_PLACEMENTS_METRIC.value]

            menu_placement_share_df = self.get_share_totals(
                numerator_df=breakout_df[keep_cols],
                metrics=[menu_placement_metric],
                breakout=breakout,
                query_filters=query_filters
            )

            menu_placement_share_df = menu_placement_share_df.rename(columns={
                menu_placement_metric['name']: MenuColNames.MENU_PLACEMENTS_SHARE_METRIC.value
            })

            if not menu_placement_share_df.empty:
                dfs.append(menu_placement_share_df)

        if not dfs:
            exit_with_status("No data found for the given filters")

        # merge the dfs on the breakout dims
        if breakouts:

            breakout_df: pd.DataFrame = dfs[0]

            for df in dfs[1:]:
                breakout_df = breakout_df.merge(df, on=breakouts, how='left')

        else:

            breakout_df = pd.concat(dfs, axis=1)

        return breakout_df
    
    def get_growth_type_label(self, growth_type: str) -> str:
        return "yoy" if growth_type == "Y/Y" else "pop"
    
    def get_growth_diff_col(self, growth_type: str) -> str:
        growth_type_label = self.get_growth_type_label(growth_type)
        return f"{growth_type_label} diff"
    
    def get_growth_pct_col(self, growth_type: str) -> str:
        growth_type_label = self.get_growth_type_label(growth_type)
        return f"{growth_type_label} %"

    def calculate_growth(self, subject_df: pd.DataFrame, subject_val_col: str, subject_val_prev_col: str, metrics: List[dict], growth_type: str = "Y/Y") -> pd.DataFrame:

        '''
        Calculate the growth for the subject.
        '''

        growth_diff_col = self.get_growth_diff_col(growth_type)
        growth_pct_col = self.get_growth_pct_col(growth_type)

        hide_percentage_metrics = [metric['name'].lower() for metric in metrics if metric.get("hide_percentage_change")]

        subject_df[growth_diff_col] = subject_df[subject_val_col] - subject_df[subject_val_prev_col]
        subject_df[growth_pct_col] = np.where(
            subject_df.index.isin(hide_percentage_metrics),
            subject_df[growth_diff_col],
            np.where(
                subject_df[subject_val_prev_col] != 0,
                np.round(subject_df[growth_diff_col] / np.abs(subject_df[subject_val_prev_col]), 6),
                np.nan
            )
        )

        return subject_df
    
    def add_subject_growth(self, subject_df: pd.DataFrame, metrics: List[dict], query_filters: List[dict], growth_period_filter: dict, subject_filter: dict, growth_type: str = "Y/Y") -> pd.DataFrame:

        '''
        Add the growth values for the subject to the subject dataframe.
        '''

        if not growth_period_filter:
            return subject_df

        subject_growth_df = self.get_breakout_data(
            metrics=metrics,
            query_filters=query_filters + [growth_period_filter, subject_filter]
        )

        subject_val_col = subject_df.columns[0]
        subject_value_prev_col = f"{subject_val_col}_prev"
        subject_growth_df = subject_growth_df.T.rename(columns={0: subject_value_prev_col})

        # merge on index of dfs
        subject_df = subject_df.merge(subject_growth_df, left_index=True, right_index=True, how='left')

        subject_df = self.calculate_growth(subject_df, subject_val_col, subject_value_prev_col, metrics, growth_type)

        subject_df.drop(columns=[subject_value_prev_col], inplace=True)

        return subject_df

    def add_quantiles(self, subject_df: pd.DataFrame, breakout_df: pd.DataFrame, breakout_dim: str) -> pd.DataFrame:

        breakout_df = self.pivot_to_metrics_on_rows(breakout_df, breakout_dim)

        for quantile, label in zip(self.quantiles, self.quantile_labels):
            breakout_df[label] = breakout_df.quantile(quantile, interpolation='nearest', axis=1)

        breakout_df = breakout_df[self.quantile_labels]

        subject_df = self.merge_on_index(subject_df, breakout_df)
        return subject_df
    
    def add_goals(self, subject_df: pd.DataFrame, peer_df: pd.DataFrame) -> pd.DataFrame:

        subject_df[self.aggressive_goal_col] = subject_df[self.quantile_labels[-1]] # TODO: What happens if the subject is higher than this?
        
        if not peer_df.empty:

            peer_df[self.benchmark_goal_col] = peer_df.mean(axis=1)
            subject_df = self.merge_on_index(subject_df, peer_df[self.benchmark_goal_col])
            subject_df.drop(columns=[self.benchmark_quantile_col], inplace=True)

        else:
            subject_df.rename(columns={self.benchmark_quantile_col: self.benchmark_goal_col}, inplace=True)
            subject_df = subject_df[[col for col in subject_df.columns if col != self.benchmark_goal_col] + [self.benchmark_goal_col]]

        return subject_df
    
    def get_facts_df(self, subject_df: pd.DataFrame, metrics: List[dict], growth_type: str) -> pd.DataFrame:
        
        facts_df = subject_df.copy()

        growth_diff_col = self.get_growth_diff_col(growth_type)
        growth_pct_col = self.get_growth_pct_col(growth_type)

        # Apply formatting for each metric
        for metric in metrics:
            metric_name = metric['name']
            row = facts_df.loc[metric_name]
            facts_df.loc[metric_name] = pd.Series({
                col: self.helper.get_formatted_num(
                    row[col],
                    metric['growth_fmt'] if col == growth_pct_col or (col == growth_diff_col and metric.get("hide_percentage_change")) else metric['fmt'],
                    signed = col == growth_diff_col
                )
                for col in facts_df.columns
            })

        # Format metric columns
        facts_df = facts_df.reset_index()
        facts_df = facts_df.rename(columns={'index': 'Metrics'})

        facts_df.insert(loc=0, column='Metric Group', value=facts_df['Metrics'].apply(lambda x: DEFAULT_METRIC_GROUP_MAPPING.get(x, x))        )

        # order df by the metrics list order
        metric_names = [metric['name'].lower() for metric in metrics]

        ordering_col = 'ordering'
        facts_df[ordering_col] = facts_df['Metrics'].apply(lambda x: metric_names.index(x.lower()))
        facts_df = facts_df.sort_values(by=ordering_col)
        facts_df.drop(columns=[ordering_col], inplace=True)

        met_renames = {metric['name'].lower(): metric.get("label", metric['name']) for metric in metrics}
        facts_df['Metrics'] = facts_df['Metrics'].apply(lambda x: met_renames.get(x.lower(), x))

        return facts_df
    
    def get_table_df(self, df: pd.DataFrame, metrics: List[dict], breakout_dim: str, query_filters: List[dict]) -> pd.DataFrame:

        table_df = df.copy()

        metric_names = [metric['name'] for metric in metrics]

        table_df.max_metadata.set_filters(query_filters)
        table_df.max_metadata.set_measures(metric_names)
        table_df.max_metadata.set_description(f"{', '.join(metric_names)} broken out by {breakout_dim}")

        return table_df
    
    def get_title_and_subtitle(self, parameters: StrategicBenchmarkParameters) -> Tuple[str, str]:

        title = old_get_filters_headline(
            [parameters.subject_filter],
            headline_seperator=", ",
            metric_props=self.metric_props,
            dim_props=self.dim_props
        )

        peer_title = old_get_filters_headline(
            parameters.peer_filters,
            headline_seperator=", ",
            metric_props=self.metric_props,
            dim_props=self.dim_props
        )

        query_filters_title = old_get_filters_headline(
            parameters.query_filters,
            headline_seperator=", ",
            metric_props=self.metric_props,
            dim_props=self.dim_props
        )

        title = f"Strategic Benchmark for {title}"

        if peer_title:
            title = f"{title} vs {peer_title}"

        if query_filters_title:
            title = f"{title} • {query_filters_title}"

        subtitle = old_get_date_label_str(parameters.date_labels, prefix="")

        return title, subtitle
    
    def run(self, parameters: StrategicBenchmarkParameters) -> StrategicBenchmarkRunResult:

        breakout_dim = parameters.subject_filter['col']
        current_period_filter = parameters.period_filters[0]
        growth_period_filter = parameters.period_filters[1] if len(parameters.period_filters) > 1 else None

        # get breakout df

        breakout_df = self.get_breakout_data(
            metrics=parameters.metrics,
            breakout=breakout_dim,
            query_filters=parameters.query_filters + ([current_period_filter] if current_period_filter else [])
        )

        subject_df = self.pivot_to_metrics_on_rows(breakout_df[breakout_df[breakout_dim].str.lower() == parameters.subject_filter['val'].lower()], breakout_dim)
        peer_df = self.pivot_to_metrics_on_rows(breakout_df[breakout_df[breakout_dim].str.lower().isin([filter['val'].lower() for filter in parameters.peer_filters])], breakout_dim)
        
        subject_df = self.add_subject_growth(subject_df, parameters.metrics, parameters.query_filters, growth_period_filter, parameters.subject_filter, parameters.growth_type)
        subject_df = self.add_quantiles(subject_df, breakout_df, breakout_dim)
        subject_df = pd.concat([subject_df, peer_df], axis=1)
        subject_df = self.add_goals(subject_df, peer_df)

        facts_df = self.get_facts_df(subject_df, parameters.metrics, parameters.growth_type)
        table_df = self.get_table_df(facts_df, parameters.metrics, breakout_dim, parameters.query_filters)

        title, subtitle = self.get_title_and_subtitle(parameters)
        warnings = self.get_warning_messages()

        result = StrategicBenchmarkRunResult(
            table_df=table_df,
            fact_dfs=[facts_df],
            followups=[],
            title=title,
            subtitle=subtitle,
            warnings=warnings
        )

        return result
    
    def create_viz(self, run_result: StrategicBenchmarkRunResult) -> SkillOutput:

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
