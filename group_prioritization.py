from __future__ import annotations

from skill_framework import SkillInput, skill, SkillParameter

from ar_analytics.defaults import default_table_layout
from analysis_classes.group_prioritization.analysis import GroupPrioritization
from analysis_classes.group_prioritization.template_parameter_setup import GroupPrioritizationTemplateParameterSetup
from analysis_classes.group_prioritization.defaults import group_prioritization_config, DEFAULT_PERIOD
from overproof_data_provider import DataProvider

import logging
from overproof_utilities import MenuColNames

logger = logging.getLogger(__name__)

@skill(
    name=group_prioritization_config.name,
    llm_name=group_prioritization_config.llm_name,
    description=group_prioritization_config.description,
    capabilities=group_prioritization_config.capabilities,
    limitations=group_prioritization_config.limitations,
    example_questions=group_prioritization_config.example_questions,
    parameter_guidance=group_prioritization_config.parameter_guidance,
    parameters=[
        SkillParameter(
            name="periods",
            constrained_to="date_filter",
            is_multi=True,
            description="If provided by the user, list time periods in a format 'q2 2023', '2021', 'jan 2023', 'mat nov 2022', 'mat q1 2021', 'ytd q4 2022', 'ytd 2023', 'ytd', 'mat', '<no_period_provided>' or '<since_launch>'. Use knowledge about today's date to handle relative periods and open ended periods. If given a range, for example 'last 3 quarters, 'between q3 2022 to q4 2023' etc, enumerate the range into a list of valid dates. Don't include natural language words or phrases, only valid dates like 'q3 2023', '2022', 'mar 2020', 'ytd sep 2021', 'mat q4 2021', 'ytd q1 2022', 'ytd 2021', 'ytd', 'mat', '<no_period_provided>' or '<since_launch>' etc.",
            default_value="ytd"
        ),
        SkillParameter(
            name="benchmark_brand",
            constrained_to=MenuColNames.BRAND_NAME_COL.value,
            description="Benchmark brand filter"
        ),
        SkillParameter(
            name="other_filters",
            constrained_to="filters"
        ),
        SkillParameter(
            name="growth_type",
            constrained_to="growth_type",
            description="Growth type",
            default_value="Y/Y"
        ),
        SkillParameter(
            name="max_prompt",
            parameter_type="prompt",
            description="Prompt being used for max response.",
            default_value=group_prioritization_config.max_prompt
        ),
        SkillParameter(
            name="insight_prompt",
            parameter_type="prompt",
            description="Prompt being used for detailed insights.",
            default_value=group_prioritization_config.insight_prompt
        ),
        SkillParameter(
            name="table_viz_layout",
            parameter_type="visualization",
            description="Table Viz Layout",
            default_value=default_table_layout
        )
    ]
)
def group_prioritization(parameters: SkillInput):

    init, sb_parameters = GroupPrioritizationTemplateParameterSetup().map_parameters(parameters=parameters)

    df_provider = DataProvider()
    init.df_provider = df_provider

    sb = GroupPrioritization(init=init)  

    sb_result = sb.run(parameters=sb_parameters)

    # TODO: Confirm if this footnote is needed
    # if df_provider.removed_nones:
    #     sb_result.general_footnote = "Many Items are not aligned with specific product details. These values are filtered from analysis and calculations to provide a more clear answer."

    return sb.create_viz(run_result=sb_result)
