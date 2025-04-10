from __future__ import annotations
from dataclasses import dataclass
import json
from types import SimpleNamespace
from typing import Optional

from skill_framework import SkillInput, SkillVisualization, skill, SkillParameter, SkillOutput, SuggestedQuestion, \
    ParameterDisplayDescription
from skill_framework.preview import preview_skill
from skill_framework.skills import ExportData
from skill_framework.layouts import wire_layout

# from ar_analytics import MarketShareBreakdown, MSBTemplateParameterSetup, ArUtils
from ar_analytics import ArUtils
from market_share_breakdown import MarketShareBreakdown, MSBTemplateParameterSetup
from ar_analytics.defaults import market_share_analysis_config, default_table_layout, get_table_layout_vars

import jinja2
import logging
import pandas as pd

from overproof_data_provider import DataProvider

logger = logging.getLogger(__name__)

# MSACONFIG should only be used for local testing
@dataclass
class MSACONFIG:
    global_view: Optional[str] = None
    market_view: Optional[str] = None
    include_drivers: Optional[str] = None
    market_cols: Optional[str] = None
    impact_calcs: Optional[str] = None
    decomposition_display_config: Optional[str] = None
    subject_metric_config: Optional[str] = None

DEFAULT_GLOBAL_VIEW = """
[
  {
    "dim": "state_name",
    "type": "share",
    "exclude_in_mkt_size": true,
    "tab_label": "State",
    "drilldown": {
      "dim": "venue_city",
      "type": "contribution"
    }
  },
  {
    "dim": "supplier_name",
    "type": "contribution",
    "exclude_in_mkt_size": false,
    "tab_label": "Supplier",
    "drilldown": {
      "dim": "state_name",
      "type": "contribution"
    }
  }
]
"""

DEFAULT_MARKET_VIEW = """
[
  {
    "dim": "product_category_name",
    "type": "share",
    "exclude_in_mkt_size": true,
    "tab_label": "Category",
    "drilldown": {
         "dim": "brand_name",
         "type": "contribution"
      }
  },
  {
    "dim": "cocktail__name",
    "type": "share",
    "exclude_in_mkt_size": true,
    "tab_label": "Cocktail"
  }
]
"""

DEFAULT_INCLUDE_DRIVERS = True

DEFAULT_MARKET_COLS = """
["state_name"]
"""

DEFAULT_IMPACT_CALCS = """"""

DEFAULT_DECOMPOSITION_DISPLAY_CONFIG = """"""

# DEFAULT_SUBJECT_METRIC_CONFIG = """
# {
#     "Metric Relationship": {
#         "menu_placements": ["pct_change"]
#     }
# }
# """

DEFAULT_SUBJECT_METRIC_CONFIG = """"""

# uncomment for local testing
default_msa_config = MSACONFIG(
    global_view=DEFAULT_GLOBAL_VIEW,
    market_view=DEFAULT_MARKET_VIEW,
    include_drivers=DEFAULT_INCLUDE_DRIVERS,
    market_cols=DEFAULT_MARKET_COLS,
    impact_calcs=DEFAULT_IMPACT_CALCS,
    decomposition_display_config=DEFAULT_DECOMPOSITION_DISPLAY_CONFIG,
    subject_metric_config=DEFAULT_SUBJECT_METRIC_CONFIG
)

# uncomment for adding to env
# default_msa_config = MSACONFIG(
#     global_view="",
#     market_view="",
#     include_drivers=DEFAULT_INCLUDE_DRIVERS,
#     market_cols="",
#     impact_calcs="",
#     decomposition_display_config="",
#     subject_metric_config=""
# )

@skill(
    name=market_share_analysis_config.name,
    llm_name=market_share_analysis_config.llm_name,
    description=market_share_analysis_config.description,
    capabilities=market_share_analysis_config.capabilities,
    limitations=market_share_analysis_config.limitations,
    example_questions=market_share_analysis_config.example_questions,
    parameter_guidance=market_share_analysis_config.parameter_guidance,
    parameters=[
        SkillParameter(
            name="metric",
            constrained_to="metrics",
            is_multi=False
        ),
        SkillParameter(
            name="growth_type",
            is_multi=False,
            constrained_values=["Y/Y", "P/P"],
            description="Growth type either Y/Y or P/P",
            default_value="Y/Y"
        ),
        SkillParameter(
            name="other_filters",
            constrained_to="filters"
        ),
        SkillParameter(
            name="limit_n",
            description="limit the number of values by this number",
            default_value=20
        ),
        SkillParameter(
            name="periods",
            constrained_to="date_filter",
            is_multi=True,
            description="If provided by the user, list time periods in a format 'q2 2023', '2021', 'jan 2023', 'mat nov 2022', 'mat q1 2021', 'ytd q4 2022', 'ytd 2023', 'ytd', 'mat', '<no_period_provided>' or '<since_launch>'. Use knowledge about today's date to handle relative periods and open ended periods. If given a range, for example 'last 3 quarters, 'between q3 2022 to q4 2023' etc, enumerate the range into a list of valid dates. Don't include natural language words or phrases, only valid dates like 'q3 2023', '2022', 'mar 2020', 'ytd sep 2021', 'mat q4 2021', 'ytd q1 2022', 'ytd 2021', 'ytd', 'mat', '<no_period_provided>' or '<since_launch>' etc."
        ),
        SkillParameter(
            name="global_view",
            parameter_type="code",
            default_value=default_msa_config.global_view
        ),
        SkillParameter(
            name="market_view",
            parameter_type="code",
            default_value=default_msa_config.market_view
        ),
        SkillParameter(
            name="include_drivers",
            parameter_type="code",
            default_value=default_msa_config.include_drivers
        ),
        SkillParameter(
            name="market_cols",
            parameter_type="code",
            default_value=default_msa_config.market_cols
        ),
        SkillParameter(
            name="impact_calcs",
            parameter_type="code",
            default_value=default_msa_config.impact_calcs
        ),
        SkillParameter(
            name="decomposition_display_config",
            parameter_type="code",
            default_value=default_msa_config.decomposition_display_config
        ),
        SkillParameter(
            name="subject_metric_config",
            parameter_type="code",
            default_value=default_msa_config.subject_metric_config
        ),
        SkillParameter(
            name="max_prompt",
            parameter_type="prompt",
            description="Prompt being used for max response.",
            default_value=market_share_analysis_config.max_prompt
        ),
        SkillParameter(
            name="insight_prompt",
            parameter_type="prompt",
            description="Prompt being used for detailed insights.",
            default_value=market_share_analysis_config.insight_prompt
        ),
        SkillParameter(
            name="table_viz_layout",
            parameter_type="visualization",
            description="Table Viz Layout",
            default_value=default_table_layout
        )
    ]
)
def market_share_analysis(parameters: SkillInput):
    print(f"Skill received following parameters: {parameters}")
    param_dict = {"periods": [], "metric": None, "limit_n": 20, "growth_type": "Y/Y", "other_filters": [], "global_view": [], "market_view": [],
                  "include_drivers": True, "market_cols": [], "impact_calcs": {}, "decomposition_display_config": {}, "subject_metric_config": {}}
    
    code_params = ["global_view", "market_view", "market_cols", "impact_calcs", "decomposition_display_config", "subject_metric_config"]

    # Update param_dict with values from parameters.arguments if they exist
    for key in param_dict:
        if hasattr(parameters.arguments, key) and getattr(parameters.arguments, key) is not None:
            param_dict[key] = getattr(parameters.arguments, key)
            if key in code_params and isinstance(param_dict[key], str) and param_dict[key]:
                try: 
                    param_dict[key] = json.loads(param_dict[key])
                except json.JSONDecodeError:
                    logger.error(f"Error decoding JSON for parameter: {key}")
                    param_dict[key] = {}

    if str(param_dict["growth_type"]).lower() not in ["y/y", 'p/p']:
        param_dict["growth_type"] = "Y/Y"

    env = SimpleNamespace(**param_dict)
    MSBTemplateParameterSetup(env=env)
    env.msa = MarketShareBreakdown(
        sql_exec=env.msb_parameters["con"],
        dim_hierarchy=env.msb_parameters["dim_hierarchy"],
        constrained_values=env.msb_parameters["constrained_values"],
        compare_date_warning_msg=env.msb_parameters["compare_date_warning_msg"],
        df_provider=DataProvider()
    )
    env.msa.env = env

    result_dfs = env.msa.run_from_env()
    print(result_dfs.keys())
    tables = env.msa.get_display_tables()
    param_info = [ParameterDisplayDescription(key=k, value=v) for k, v in env.msa.paramater_display_infomation.items()]

    insights_dfs = [env.msa.subject_facts, env.msa.bottom_peers_facts, env.msa.top_peers_facts, env.msa.bottom_breakouts_facts, env.msa.top_breakouts_facts, env.msa.metric_driver_challenges_facts, env.msa.df_notes]
    followups = env.msa.suggestions

    viz, insights, final_prompt, export_data = render_layout(tables,
                                                            env.msa.title,
                                                            env.msa.subtitle,
                                                            insights_dfs,
                                                            env.msa.warning_message,
                                                            parameters.arguments.max_prompt,
                                                            parameters.arguments.insight_prompt, 
                                                            parameters.arguments.table_viz_layout)

    return SkillOutput(
        final_prompt=final_prompt,
        narrative=None,
        visualizations=viz,
        parameter_display_descriptions=param_info,
        followup_questions=[SuggestedQuestion(label=f.get("label"), question=f.get("question")) for f in followups if
                            f.get("label")],
        export_data=[ExportData(name=name, data=df) for name, df in export_data.items()]
    )

def transform_df_into_datatable_data(df):

    return df.fillna('N/A').to_numpy().tolist()

    if "parent_dim_member" in df.columns and "is_collapsible" in df.columns:

        row_data = []

        parent_dim_member_idx = df.columns.get_loc("parent_dim_member")
        is_collapsible_idx = df.columns.get_loc("is_collapsible")

        for index, row in df.iterrows():

            is_collapsible = row[is_collapsible_idx]
            parent_dim_member = row[parent_dim_member_idx]

            if not is_collapsible and parent_dim_member != "":
                # get row without parent_dim_member and is_collapsible

                row_data.append(row[:parent_dim_member_idx] + row[parent_dim_member_idx+2:])
            else:

                node = {"data"}

    else:
        return df.fillna('N/A').to_numpy().tolist()

def get_data(df):
    data = []
    has_subject = 'is_subject' in df.columns

    for _, row in df.iterrows():
        new_row = []
        is_subject = has_subject and bool(row['is_subject'])
        click_followup = row.get("msg")

        for col, val in row.items():
            # Skip the is_subject column from output
            if col in ['is_subject', 'is_collapsible', 'msg']:
                continue

            if pd.isna(val):
                val = 'N/A'

            if is_subject:
                val = {'style': {'background-color': '#FFF0BE'}, 'value': val}

            if col == "msg":
                val = {}

            new_row.append(val)

        if click_followup:
            data.append({"data": new_row, "onClick": {"args": click_followup, "event": "askQuestion"}})
        else:
            data.append(new_row)
    return data

def get_table_layout_vars_msa(df):
    """
    Generates table layout variables from a DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame.

    Returns:
        dict: A dictionary containing the table layout variables.
            - "data" (list): A list of lists representing the table data.
            - "col_defs" (list): A list of dictionaries representing the column definitions.
    """
    table_vars = {}
    data = get_data(df)
    col_defs = []
    columns = list(df.columns)
    for ix, col in enumerate(columns):
        if col in ['is_subject', 'is_collapsible', 'msg']:
            continue
        if ix == 0:
            col_defs.append({"name": col, "style": {"textAlign": "left", "white-space": "pre"}})
        else:
            col_defs.append({"name": col})

    table_vars["data"] = data
    table_vars["col_defs"] = col_defs
    return table_vars

def render_layout(tables, title, subtitle, insights_dfs, warnings, max_prompt, insight_prompt, viz_layout):
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

    general_vars = {
        "headline": title if title else "Total",
        "sub_headline": subtitle or "Market Share Analysis",
        "hide_growth_warning": False if warnings else True,
        "exec_summary": insights if insights else "No Insights.",
        "warning": warnings,
        "hide_footer": True
    }

    viz_layout = json.loads(viz_layout)

    for name, table in tables.items():
        export_data[name] = table
        # dim_note = find_footnote(footnotes, table)
        # hide_footer = False if dim_note else True

        table_vars = get_table_layout_vars_msa(table)
        # table_vars["hide_footer"] = hide_footer
        rendered = wire_layout(viz_layout, {**general_vars, **table_vars})
        viz_list.append(SkillVisualization(title=name, layout=rendered))

    return viz_list, insights, max_response_prompt, export_data

if __name__ == '__main__':
    skill_input: SkillInput = market_share_analysis.create_input(
        arguments=
    {
        "metric": "menu_placements_share",
        "periods": ["2024"],
        "other_filters": [{"dim": "product_category_name", "op": "=", "val": "vodka"}]
    }
)
    out = market_share_analysis(skill_input)
    preview_skill(market_share_analysis, out)