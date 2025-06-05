import pandas as pd
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

    def run(self, parameters: StrategicBenchmarkParameters) -> StrategicBenchmarkRunResult:

        df = pd.DataFrame({"test": [1,2,3,4]})

        result = StrategicBenchmarkRunResult(
            df=df,
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
