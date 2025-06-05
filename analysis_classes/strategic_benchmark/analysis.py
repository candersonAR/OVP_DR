import pandas as pd
from ar_analytics import pull_data
from skill_framework import ExportData, SkillOutput

from analysis_classes.strategic_benchmark.defaults import StrategicBenchmarkInit, StrategicBenchmarkParameters, StrategicBenchmarkRunResult
from overproof_utilities import OverproofSharedFn

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

import json
import jinja2
from ar_analytics import ArUtils

from skill_framework import SkillVisualization, SkillOutput, SuggestedQuestion
from skill_framework.skills import ExportData
from skill_framework.layouts import wire_layout

from ar_analytics.defaults import get_table_layout_vars

def find_footnote(footnotes, df, general_footnote=None):
    footnotes = footnotes or {}
    for col in df.columns:
        if col in footnotes:
            dim_note = footnotes.get(col)
            if general_footnote:
                return dim_note + "\n" + general_footnote
            return dim_note
    return general_footnote

def render_layout(tables, title, subtitle, insights_dfs, warnings, footnotes, general_footnote, max_prompt, insight_prompt, viz_layout):
    facts = []
    for i_df in insights_dfs:
        facts.append(i_df.to_dict(orient='records'))

    insight_template = jinja2.Template(insight_prompt).render(**{"facts": facts})
    max_response_prompt = jinja2.Template(max_prompt).render(**{"facts": facts})

    # adding insights
    ar_utils = ArUtils()
    insights = ar_utils.get_llm_response(insight_template)
    viz_list = []
    export_data = {}

    general_vars = {"headline": title if title else "Total",
                    "sub_headline": subtitle or "Breakout Analysis",
                    "hide_growth_warning": False if warnings else True,
                    "exec_summary": insights if insights else "No Insights.",
                    "warning": warnings}

    viz_layout = json.loads(viz_layout)

    for name, table in tables.items():
        export_data[name] = table
        dim_note = find_footnote(footnotes, table, general_footnote)
        hide_footer = False if dim_note else True
        table_vars = get_table_layout_vars(table)
        table_vars["hide_footer"] = hide_footer
        table_vars["footer"] = f"*{dim_note.strip()}" if dim_note else "No additional info."
        rendered = wire_layout(viz_layout, {**general_vars, **table_vars})
        viz_list.append(SkillVisualization(title=name, layout=rendered))

    return viz_list, insights, max_response_prompt, export_data
