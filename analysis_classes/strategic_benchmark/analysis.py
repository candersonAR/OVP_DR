from typing import List
import pandas as pd
import numpy as np
from ar_analytics import pull_data
from skill_framework import ExportData, SkillOutput

from analysis_classes.strategic_benchmark.defaults import StrategicBenchmarkInit, StrategicBenchmarkParameters, StrategicBenchmarkRunResult
from overproof_utilities import OverproofSharedFn
from overproof_visualization_utilities import render_layout

class StrategicBenchmark:
    def __init__(self, init: StrategicBenchmarkInit):

        self.con = init.sql_exec
        self.dim_hierarchy = init.dim_hierarchy
        self.compare_date_warning_msg = init.compare_date_warning_msg
        self.pills = init.pills
        self.metric_props = init.metric_props
        self.dim_props = init.dim_props

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

    def calculate_growth(self, subject_df: pd.DataFrame, subject_val_col: str, subject_val_prev_col: str, growth_type: str = "Y/Y") -> pd.DataFrame:

        '''
        Calculate the growth for the subject.
        '''

        growth_type_label = "yoy" if growth_type == "Y/Y" else "pop"

        subject_df[f"{growth_type_label} diff"] = subject_df[subject_val_col] - subject_df[subject_val_prev_col]
        subject_df[f"{growth_type_label} %"] = np.where(
            subject_df[subject_val_prev_col] != 0,
            np.round(subject_df[f"{growth_type_label} diff"] / np.abs(subject_df[subject_val_prev_col]), 6),
            np.nan
        )

        return subject_df
    
    def add_subject_growth(self, subject_df: pd.DataFrame, metrics: List[dict], query_filters: List[dict], growth_period_filter: dict, subject_filter: dict, growth_type: str = "Y/Y") -> pd.DataFrame:

        '''
        Add the growth values for the subject to the subject dataframe.
        '''

        if not growth_period_filter:
            return subject_df

        subject_growth_df = self.pull_data_func(
            metrics=metrics,
            filters=query_filters + [growth_period_filter, subject_filter]
        )

        subject_val_col = subject_df.columns[0]
        subject_value_prev_col = f"{subject_val_col}_prev"
        subject_growth_df = subject_growth_df.T.rename(columns={0: subject_value_prev_col})

        # merge on index of dfs
        subject_df = subject_df.merge(subject_growth_df, left_index=True, right_index=True, how='left')

        subject_df = self.calculate_growth(subject_df, subject_val_col, subject_value_prev_col, growth_type)

        subject_df.drop(columns=[subject_value_prev_col], inplace=True)

        return subject_df

    def add_quantiles(self, subject_df: pd.DataFrame, breakout_df: pd.DataFrame, breakout_dim: str, metrics: List[dict]) -> pd.DataFrame:

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
            subject_df = self.merge_on_index(subject_df, peer_df)
            subject_df.drop(columns=[self.benchmark_quantile_col], inplace=True)

        else:
            subject_df.rename(columns={self.benchmark_quantile_col: self.benchmark_goal_col}, inplace=True)

        return subject_df
    
    def get_facts_df(self, subject_df: pd.DataFrame, metrics: List[dict]) -> pd.DataFrame:
        
        
    
    def run(self, parameters: StrategicBenchmarkParameters) -> StrategicBenchmarkRunResult:

        breakout_dim = parameters.subject_filter['col']

        current_period_filter = parameters.period_filters[0]
        growth_period_filter = parameters.period_filters[1] if len(parameters.period_filters) > 1 else None

        # get breakout df

        breakout_df = self.pull_data_func(
            metrics=parameters.metrics,
            breakouts=[breakout_dim],
            filters=parameters.query_filters + [current_period_filter]
        )

        subject_df = self.pivot_to_metrics_on_rows(breakout_df[breakout_df[breakout_dim].str.lower() == parameters.subject_filter['val'].lower()], breakout_dim)
        peer_df = self.pivot_to_metrics_on_rows(breakout_df[breakout_df[breakout_dim].str.lower().isin([filter['val'].lower() for filter in parameters.peer_filters])], breakout_dim)
        
        subject_df = self.add_subject_growth(subject_df, parameters.metrics, parameters.query_filters, growth_period_filter, parameters.subject_filter)
        subject_df = self.add_quantiles(subject_df, breakout_df, breakout_dim, parameters.metrics)
        subject_df = self.merge_on_index(subject_df, peer_df)
        subject_df = self.add_goals(subject_df, peer_df)

        result = StrategicBenchmarkRunResult(
            df=subject_df,
            fact_dfs=[pd.DataFrame(self.notes)],
            followups=[]
        )

        return result
    
    def create_viz(self, run_result: StrategicBenchmarkRunResult) -> SkillOutput:

        tables = {"table": run_result.df}
        warnings = None
        footnotes = {}
        general_footnote = None

        title = "Strategic Benchmark"
        subtitle = "Strategic Benchmark"

        viz, insights, final_prompt, export_data = render_layout(
            tables,
            title,
            subtitle,
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
