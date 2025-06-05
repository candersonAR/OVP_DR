from __future__ import annotations
from types import SimpleNamespace

from skill_framework import SkillInput, SkillVisualization, skill, SkillParameter, SkillOutput, SuggestedQuestion, ParameterDisplayDescription
from skill_framework.preview import preview_skill
from skill_framework.skills import ExportData
from skill_framework.layouts import wire_layout

from ar_analytics import BreakoutAnalysisTemplateParameterSetup, ArUtils
from ar_analytics.helpers.utils import exit_with_status
from ar_analytics.defaults import dimension_breakout_config, default_table_layout, get_table_layout_vars
from overproof_dimension_breakout import OverproofBreakoutAnalysis
from overproof_data_provider import DataProvider
from overproof_utilities import MenuColNames

import jinja2
import logging
import json

from overproof_utilities import map_cocktails

logger = logging.getLogger(__name__)

@skill(
    name="Cocktail Uplift Performance",
    llm_name="cocktail_uplift_performance",
    description=dimension_breakout_config.description,
    capabilities=dimension_breakout_config.capabilities,
    limitations=dimension_breakout_config.limitations,
    example_questions=dimension_breakout_config.example_questions,
    parameter_guidance=dimension_breakout_config.parameter_guidance,
    parameters=[
        SkillParameter(
            name="periods",
            constrained_to="date_filter",
            is_multi=True,
            description="If provided by the user, list time periods in a format 'q2 2023', '2021', 'jan 2023', 'mat nov 2022', 'mat q1 2021', 'ytd q4 2022', 'ytd 2023', 'ytd', 'mat', '<no_period_provided>' or '<since_launch>'. Use knowledge about today's date to handle relative periods and open ended periods. If given a range, for example 'last 3 quarters, 'between q3 2022 to q4 2023' etc, enumerate the range into a list of valid dates. Don't include natural language words or phrases, only valid dates like 'q3 2023', '2022', 'mar 2020', 'ytd sep 2021', 'mat q4 2021', 'ytd q1 2022', 'ytd 2021', 'ytd', 'mat', '<no_period_provided>' or '<since_launch>' etc."
        ),
        SkillParameter(
            name="limit_n",
            description="limit the number of values by this number",
            default_value=10
        ),
        SkillParameter(
            name="other_filters",
            constrained_to="filters"
        ),
        SkillParameter(
            name="max_prompt",
            parameter_type="prompt",
            description="Prompt being used for max response.",
            default_value=dimension_breakout_config.max_prompt
        ),
        SkillParameter(
            name="insight_prompt",
            parameter_type="prompt",
            description="Prompt being used for detailed insights.",
            default_value=dimension_breakout_config.insight_prompt
        ),
        SkillParameter(
            name="table_viz_layout",
            parameter_type="visualization",
            description="Table Viz Layout",
            default_value=default_table_layout
        )
    ]
)

def uplift_performance(parameters: SkillInput):
    print(f"Skill received following parameters: {parameters.arguments}")

    if MenuColNames.BRAND_NAME_COL.value not in [f.get("dim") for f in parameters.arguments.other_filters] and MenuColNames.SUPPLIER_NAME_COL.value not in [f.get("dim") for f in parameters.arguments.other_filters]:
        exit_with_status("Brand name or supplier name filter is required for this skill! Please ask the user to provide a brand name or supplier name to filter by.")

    metric__menu_mentions_props = {'name': MenuColNames.UPLIFT_PERFORMANCE_MENU_MENTIONS_METRIC.value, 'label': 'Menu Mentions', 'sql': None, 'col': 'menu_mentions', 'metric_type': None, 'is_share': None, 'fmt': ',.2f', 'growth_fmt': ',.2f', 'hide_percentage_change': True}
    metric__vpo_with_props = {'name': MenuColNames.UPLIFT_PERFORMANCE_VPO_WITH_METRIC.value, 'label': 'VPO With', 'sql': None, 'col': 'vpo_with', 'metric_type': None, 'is_share': None, 'fmt': ',.2f', 'growth_fmt': ',.2f', 'hide_percentage_change': True}
    metric__vpo_without_props = {'name': MenuColNames.UPLIFT_PERFORMANCE_VPO_WITHOUT_METRIC.value, 'label': 'VPO Without', 'sql': None, 'col': 'vpo_without', 'metric_type': None, 'is_share': None, 'fmt': ',.2f', 'growth_fmt': ',.2f', 'hide_percentage_change': True}
    uplift_performance_additional_metrics = [prop.get("name") for prop in [metric__menu_mentions_props, metric__vpo_with_props, metric__vpo_without_props]]

    required_breakouts = [MenuColNames.INGREDIENT_OF_COCKTAIL_NAME_COL.value]
    required_metrics = [MenuColNames.COCKTAIL_UPLIFT_METRIC.value] + uplift_performance_additional_metrics
    param_dict = {"periods": [], "limit_n": 10, "metrics": required_metrics, "breakouts": required_breakouts, "other_filters": [], "calculated_metric_filters": None, "growth_type": None, "growth_trend": None}
    
    # Update param_dict with values from parameters.arguments if they exist
    for key in param_dict:
        if hasattr(parameters.arguments, key) and getattr(parameters.arguments, key) is not None:
            param_dict[key] = getattr(parameters.arguments, key)

    env = SimpleNamespace(**param_dict)
    BreakoutAnalysisTemplateParameterSetup(env=env)
    env.metric_props.update({
        MenuColNames.UPLIFT_PERFORMANCE_MENU_MENTIONS_METRIC.value: metric__menu_mentions_props,
        MenuColNames.UPLIFT_PERFORMANCE_VPO_WITH_METRIC.value: metric__vpo_with_props,
        MenuColNames.UPLIFT_PERFORMANCE_VPO_WITHOUT_METRIC.value: metric__vpo_without_props
    })

    # Mapping cocktails -> ingredient of cocktails and vice versa
    updated_filters, updated_breakouts, updated_dim_hierarchy = map_cocktails(
        env.breakout_parameters["query_filters"], 
        env.breakout_parameters["breakouts"], 
        env.breakout_parameters["dim_hierarchy"],
        env.dim_props
    )
    env.breakout_parameters["query_filters"] = updated_filters

    updated_metrics = [env.metric_props[m] for m in env.metric_props if m in required_metrics]
    updated_filters = updated_filters + env.breakout_parameters["period_filters"]

    env.breakout_parameters["breakouts"] = updated_breakouts
    env.breakout_parameters["dim_hierarchy"] = updated_dim_hierarchy
    
    df_provider = DataProvider()
    env.ba = OverproofBreakoutAnalysis.from_env(env=env, df_provider=df_provider)
    _ = env.ba.run_from_env()

    general_footnote = ""
    if df_provider.removed_nones:
        general_footnote = "Many Items are not aligned with specific product details. These values are filtered from analysis and calculations to provide a more clear answer."

    tables = env.ba.get_display_tables()
    param_info = [ParameterDisplayDescription(key=k, value=v) for k, v in env.ba.paramater_display_infomation.items()]

    insights_dfs = [env.ba.df_notes, env.ba.breakout_facts, env.ba.subject_facts]
    followups = env.ba.get_suggestions()

    viz, insights, final_prompt, export_data = render_layout(tables,
                                                             env.ba.title,
                                                             env.ba.subtitle,
                                                             insights_dfs,
                                                             env.ba.warning_message,
                                                             env.ba.footnotes,
                                                             general_footnote,
                                                             parameters.arguments.max_prompt,
                                                             parameters.arguments.insight_prompt,
                                                             parameters.arguments.table_viz_layout)

    return SkillOutput(
        final_prompt=final_prompt,
        narrative=None,
        visualizations=viz,
        parameter_display_descriptions=param_info,
        followup_questions=[SuggestedQuestion(label=f.get("label"), question=f.get("question")) for f in followups if f.get("label")],
        export_data=[ExportData(name=name, data=df) for name, df in export_data.items()]
    )


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

if __name__ == '__main__':
    skill_input = uplift_performance.create_input(
        arguments={'periods': ["Q1 2024"],
                   'other_filters': [{"dim": "brand_name", "op": "=", "val": ["Papa's Pilar"]}]})

    out = uplift_performance(skill_input)
    preview_skill(uplift_performance, out)
