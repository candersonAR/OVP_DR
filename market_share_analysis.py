from __future__ import annotations
from dataclasses import dataclass
import json
from types import SimpleNamespace
from typing import Optional

from skill_framework import SkillInput, SkillVisualization, skill, SkillParameter, SkillOutput, SuggestedQuestion, \
    ParameterDisplayDescription
from skill_framework.preview import preview_skill
from skill_framework.skills import ExportData

# from ar_analytics import MarketShareBreakdown, MSBTemplateParameterSetup, ArUtils
from ar_analytics import ArUtils
from market_share_breakdown import MarketShareBreakdown, MSBTemplateParameterSetup
from ar_analytics.defaults import market_share_analysis_config

import jinja2
import logging

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
                                                            parameters.arguments.insight_prompt)

    return SkillOutput(
        final_prompt=final_prompt,
        narrative=insights,
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

def render_layout(tables, title, subtitle, insights_dfs, warnings, max_prompt, insight_prompt):
    height = 80
    template = jinja2.Template(TEMPLATE)
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

    for name, table in tables.items():
        export_data[name] = table
        template_vars = {
            'dfs': [transform_df_into_datatable_data(table)],
            "height": height,
            "title": title,
            "subtitle": subtitle,
            "warnings": warnings
        }
        rendered = template.render(**template_vars)
        viz_list.append(SkillVisualization(title=name, layout=rendered))
    return viz_list, insights, max_response_prompt, export_data

TEMPLATE = """
{
"type": "Document",
"rows": 100,
"columns": 160,
"rowHeight": "1.11%",
"colWidth": "0.625%",
"gap": "0px",
"style": {
    "backgroundColor": "white",
    "border": "1px solid #ccc",
    "width": "100%",
    "height": "100%"
},
 "children": [
    {% set ns = namespace(counter=0) %}
    {
            "name": "mainTitle",
            "type": "Header",
            "row": 0,
            "column": 1,
            "width": 120,
            "height": 2,
            "style": {
                "textAlign": "left",
                "verticalAlign": "middle",
                "fontSize": "18px",
                "fontWeight": "bold",
                "color": "#333",
                "fontFamily": "Arial, sans-serif"
            },
            "text": "{{title}}"
    },
    {
            "name": "subtitle",
            "type": "Header",
            "row": 4,
            "column": 1,
            "width": 120,
            "height": 2,
            "style": {
                "textAlign": "left",
                "verticalAlign": "middle",
                "fontSize": "12px",
                "color": "#888",
                "fontFamily": "Arial, sans-serif"
            },
            "text": "{{subtitle}}"
    },
    {% set chart_start = 7 %}
    {% if warnings %}
        {% set chart_start = 10 %}
        {
                "name": "subtitle",
                "type": "Header",
                "row": 7,
                "column": 1,
                "width": 158,
                "height": 2,
                "style": {
                    "textAlign": "left",
                    "verticalAlign": "middle",
                    "color": "#333",
                    "fontFamily": "Arial, sans-serif",
                    "backgroundColor": "#FFF8E1",
                    "borderRadius": "10px"
                },
                "text": "{{warnings}}"
        },
    {% endif %}
    {% for df in dfs %}
        {
        "type": "DataTable",
        "row": {{ns.counter + chart_start}},
        "column": 1,
        "width": 158,
        "height": {{height}},
        "columns": [
            {% set total_cols = df.columns | length  %}
            {% for col in df.columns %}
                {% if loop.index0 == (df.columns | length) - 1 %}
                    {"name": "{{ col }}"}
                {% elif loop.index0 == 0 %}
                    {"name": "{{ col }}", "style": {"textAlign": "left", "white-space": "pre"}},
                {% else %}
                    {"name": "{{ col }}"},
                {% endif %}
            {% endfor %}
        ],
        "data": {{ df | tojson }},
        "styles": {
                    "alternateRowColor": "#f9f9f9",
                    "fontFamily": "Arial, sans-serif",
                    "th": {
                        "backgroundColor": "#FOFOFO",
                        "color": "#000000",
                        "fontWeight": "bold"
                    },
                    "caption": {
                        "backgroundColor": "#32ea05",
                        "color": "#000000",
                        "fontWeight": "bold",
                        "fontSize": "10pt"
                    }
        }
    }{% if not loop.last %},{% endif %}
    {% set ns.counter = height*loop.index %}
    {% endfor %}
]
}
"""

if __name__ == '__main__':
    skill_input: SkillInput = market_share_analysis.create_input(
        arguments={'metric': "sales", 'periods': ["2022"], 'other_filters': [{"val": ["barilla"],"dim": "brand","op": "="},  {
      "val": [
        "semolina"
      ],
      "dim": "sub_category",
      "op": "="
    }]})
    out = market_share_analysis(skill_input)
    preview_skill(market_share_analysis, out)